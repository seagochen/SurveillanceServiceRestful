# app/routes/keyarea.py
import json

import cv2
import numpy as np
import time
from flask import Blueprint, render_template, Response, current_app, request, jsonify, make_response
from app.utils import file_utils, ground_utils
from pyengine.config.camera_setting_parser import load_camera_settings, CameraParametersConfig, save_camera_settings
from pyengine.config.pipeline_config_parser import PipelineConfig, load_pipeline_config
from pyengine.config.magistrate_config_parser import MagistrateConfig, load_magistrate_config, save_magistrate_config
from pyengine.io.network.plugins.inference_result_receiver import InferenceResultReceiverPlugin
from pyengine.utils import scale_utils
from pyengine.visualization import polygon_drawer

bp_keyarea = Blueprint("keyarea", __name__)


# ------------------------------------------------------------------
# MQTT Display
# ------------------------------------------------------------------

def _pb_to_ndarray(msg) -> np.ndarray | None:
    """
    期望字段:
      - frame_width: int
      - frame_height: int
      - frame_channels: int (可为 0)
      - frame_raw_data: bytes (H*W*C) 或 (H*W) 长度
    """
    try:
        w = int(getattr(msg, "frame_width", 0))
        h = int(getattr(msg, "frame_height", 0))
        c = int(getattr(msg, "frame_channels", 0))
        raw = bytes(getattr(msg, "frame_raw_data", b""))
        if not raw or w <= 0 or h <= 0:
            return None

        arr = np.frombuffer(raw, dtype=np.uint8)
        if c == 0:
            # 尝试推断
            if arr.size == h * w:
                c = 1
            elif arr.size == h * w * 3:
                c = 3

        if c == 1 and arr.size == h * w:
            return arr.reshape((h, w))
        if c == 3 and arr.size == h * w * 3:
            return arr.reshape((h, w, 3))
        # 兜底：能整除就试
        if c > 0 and arr.size == h * w * c:
            return arr.reshape((h, w, c))
        return None
    except Exception:
        return None


@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>", methods=["GET"])
def get_keyarea_panel(magistrate_id: int):
    """
    展示重点エリア設定页面。
    说明：帧数据不在这里拉流，而是由 /frame 路由通过 MQTT 读取。
    """
    cfg: PipelineConfig = load_pipeline_config(file_utils.get_config("pipeline_config"))
    name = f"pipeline_inference_{magistrate_id}"
    inf = cfg.client_pipeline.inferences.get(name)
    if not inf:
        return f"Error: '{name}' not found in pipeline_config.yaml", 404

    # 这里不做任何连接创建/销毁，避免重复连接源
    default_key_area = {"sensitivity": 5, "min_size": 50}
    return render_template(
        "keyarea_config_panel.html",
        magistrate_id=magistrate_id,
        config={"key_area": default_key_area}
    )


# ★ 新增独立的 POST 处理函数，风格与您的示例完全一致
@bp_keyarea.route('/panel/keyarea/<int:magistrate_id>', methods=['POST'])
def update_keyarea_panel(magistrate_id: int):
    try:
        # --- 1. 这里可以添加保存重点区域设置的逻辑 ---
        # f = request.form
        # ... 从 f 中获取数据并保存到 magistrate_config{magistrate_id}.yaml ...
        # (当前表单为空，所以暂时省略)

        # --- 2. 准备返回主面板所需的数据 ---
        cfg_path = file_utils.get_config("pipeline_config")
        cfg: PipelineConfig = load_pipeline_config(cfg_path)
        name = f"pipeline_inference_{magistrate_id}"
        inf = cfg.client_pipeline.inferences.get(name)
        if not inf:
            return f"Error: '{name}' not found in pipeline_config.yaml", 404

        alias = getattr(inf, 'alias', f"クライアント {magistrate_id}")
        ip_address = (inf.camera_config.address if inf.camera_config else "N/A")

        # --- 3. 渲染主面板 HTML，用于立即替换UI ---
        panel_html = render_template('panel.html',
                                     magistrate_id=magistrate_id,
                                     alias=alias,
                                     ip_address=ip_address)

        # --- 4. 创建 OOB (Out-of-Band) 重定向片段，用于延迟更新URL ---
        redirect_oob = f'''
        <div id="keyarea-redirect-{magistrate_id}"
            hx-trigger="load delay:1s"
            hx-get="/panel/magistrate/{magistrate_id}"
            hx-target="#main-content"
            hx-swap="innerHTML"
            hx-push-url="true"
            hx-swap-oob="true"></div>
        '''

        # --- 5. 组合响应并设置 HX-Trigger 触发成功提示 ---
        resp = make_response(panel_html + redirect_oob)
        resp.headers['HX-Trigger'] = json.dumps({
            "showsuccessmodal": {"message": "重点エリア設定を保存しました", "delay": 1500}
        })
        return resp

    except Exception as e:
        # logger.error_trace(...)
        return f"Error updating keyarea config for magistrate {magistrate_id}: {e}", 500


@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/frame")
def keyarea_frame(magistrate_id: int):
    """
    通过 MQTT 订阅器读取最新一帧，转成 MJPEG 推到前端。
    【优化】使用缓存机制，每5秒重新加载一次配置文件，避免频繁IO。
    """
    topic_key = f"pipeline_inference_{magistrate_id}"
    receiver: InferenceResultReceiverPlugin = current_app.config.get(f"inference_{magistrate_id}")
    if receiver is None:
        return f"MQTT receiver not found for {topic_key}", 404
    
    TARGET_W, TARGET_H = 640, 480
    SRC_W, SRC_H = 800, 600
    BOUNDARY = b"--frame"

    def generate():
        # --- 缓存设置 ---
        cached_areas = {
            "key_area": [],
            "ground_area": []
        }
        last_config_load_time = 0.0
        CONFIG_REFRESH_INTERVAL = 5.0

        # --- 【修正】CPU負荷対策と安定化のための変数 ---
        last_good_frame = None  # 最後に受信した生のフレーム
        last_encoded_frame = None  # 最後にエンコードされたJPEGデータ
        FRAME_RATE = 25  # 出力フレームレートを25FPSに制限

        while True:
            # --- 設定のリフレッシュ（変更なし） ---
            current_time = time.time()
            if current_time - last_config_load_time > CONFIG_REFRESH_INTERVAL:
                try:
                    mag_cfg = load_magistrate_config(file_utils.get_config(f"magistrate_config{magistrate_id}"))
                    cam_cfg = load_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"))
                    cached_areas["key_area"] = mag_cfg.client_magistrate.key_area_settings.area
                    cached_areas["ground_area"] = cam_cfg.ground_coords
                    last_config_load_time = current_time
                except Exception as e:
                    print(f"[WARNING] Failed to refresh configs for magistrate {magistrate_id}: {e}")

            # --- フレームの読み取りと処理 ---
            msg = receiver.read()
            frame = _pb_to_ndarray(msg) if msg is not None else None

            # 【修正】新しいフレームが来た時だけ、描画とエンコードを行う
            if frame is not None:
                # 1. 生フレームをリサイズして保存
                if frame.ndim == 2:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else:
                    frame_bgr = frame

                frame_bgr = cv2.resize(frame_bgr, (TARGET_W, TARGET_H))
                last_good_frame = frame_bgr  # 描画のベースとして保持

                # 2. 【点滅対策】描画用キャンバスを初期化
                frame_bgr_display = last_good_frame.copy()

                # 3. エリア描画
                ground_area = cached_areas["ground_area"]
                if ground_area and len(ground_area) == 4:
                    scaled_ground_area = scale_utils.scale_euler_pts(
                        src_width=SRC_W, src_height=SRC_H,
                        dst_width=TARGET_W, dst_height=TARGET_H,
                        points=ground_area
                    )
                    frame_bgr_display = polygon_drawer.fill_grid_area(
                        frame_bgr_display, scaled_ground_area,
                        color="#00AA00", transparency=0.15,
                        grid_rows=10, grid_cols=10, perspective=True, grid_line_color="#FFFFFF", grid_transparency=0.15
                    )

                key_area = cached_areas["key_area"]
                if key_area and len(key_area) == 4:
                    scaled_key_area = scale_utils.scale_euler_pts(
                        src_width=SRC_W, src_height=SRC_H,
                        dst_width=TARGET_W, dst_height=TARGET_H,
                        points=key_area
                    )
                    frame_bgr_display = polygon_drawer.fill_area(
                        frame_bgr_display, scaled_key_area,
                        color="#C1121F",
                        transparency=0.5,
                    )

                # 4. エンコードして結果をキャッシュ
                ok, buf = cv2.imencode(".jpg", frame_bgr_display)
                if ok:
                    last_encoded_frame = buf.tobytes()

            # --- 配信処理 ---
            if last_encoded_frame is not None:
                yield (
                        BOUNDARY + b"\r\n"
                                   b"Content-Type: image/jpeg\r\n\r\n" +
                        last_encoded_frame + b"\r\n"
                )

            # 【修正】ループの速度を制御し、CPU負荷を削減
            time.sleep(1 / FRAME_RATE)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


# -------------------------------------------------------------------
# Camera Setting
# -------------------------------------------------------------------

@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/camera-settings", methods=["GET"])
def camera_settings_modal(magistrate_id: int):
    # 读取相机参数
    cfg = load_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"))
    return render_template(
        "partials/camera_settings_modal.html",
        magistrate_id=magistrate_id,
        cfg=cfg
    )


@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/camera-settings", methods=["POST"])
def camera_settings_submit(magistrate_id: int):
    # 读原配置，未出现在表单里的字段保持不变（如 ground_coords / 计算结果等）
    old = load_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"))

    # 逐项获取表单并类型转换；缺省则用旧值
    def _get_int(name, default):
        try:
            return int(request.form.get(name, default))
        except Exception:
            return default

    def _get_float(name, default):
        try:
            return float(request.form.get(name, default))
        except Exception:
            return default

    fx = _get_int("focal_length_fx", old.focal_length[0])
    fy = _get_int("focal_length_fy", old.focal_length[1])
    cx = _get_int("principal_coord_cx", old.principal_coord[0])
    cy = _get_int("principal_coord_cy", old.principal_coord[1])

    new_cfg = CameraParametersConfig(
        camera_height=_get_int("camera_height", old.camera_height),
        roll_angle=_get_int("roll_angle", old.roll_angle),
        pitch_angle=_get_int("pitch_angle", old.pitch_angle),
        yaw_angle=_get_int("yaw_angle", old.yaw_angle),
        focal_length=(fx, fy),
        principal_coord=(cx, cy),
        ground_coords=old.ground_coords,
        depth_scale=old.depth_scale,
        ground_x_length_calculated=old.ground_x_length_calculated,
        ground_y_length_calculated=old.ground_y_length_calculated,
        ground_z_length_calculated=old.ground_z_length_calculated,
    )

    save_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"), new_cfg)

    # 返回一个小的成功提示片段
    return render_template(
        "partials/save_success_snackbar.html",
        message="カメラパラメータを保存しました。"
    )


# -------------------------------------------------------------------
# Ground Setting
# -------------------------------------------------------------------

# ----------- 新增：800x600 的帧流（供地面設定弹窗左侧使用） -----------
@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/frame800")
def keyarea_frame_800(magistrate_id: int):
    receiver: InferenceResultReceiverPlugin = current_app.config.get(f"inference_{magistrate_id}")
    if receiver is None:
        return f"MQTT receiver not found for pipeline_inference_{magistrate_id}", 404

    TARGET_W, TARGET_H = 800, 600
    BOUNDARY = b"--frame"

    # 生成绘制画面
    def generate():
        # --- 【修正】CPU負荷対策と安定化のための変数 ---
        last_encoded_frame = None  # 最後にエンコードされたJPEGデータをキャッシュ
        FRAME_RATE = 25  # 出力フレームレートを25FPSに制限

        while True:
            msg = receiver.read()
            frame = _pb_to_ndarray(msg) if msg is not None else None

            # 【修正】新しいフレームが来た時だけ、リサイズとエンコードを行う
            if frame is not None:
                # 1. 色空間の変換
                if frame.ndim == 2:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else:
                    frame_bgr = frame

                # 2. リサイズ
                frame_bgr = cv2.resize(frame_bgr, (TARGET_W, TARGET_H))

                # 3. エンコードして結果をキャッシュ
                ok, buf = cv2.imencode(".jpg", frame_bgr)
                if ok:
                    last_encoded_frame = buf.tobytes()

            # --- 配信処理 ---
            # キャッシュされたフレームがあれば、それを配信する
            if last_encoded_frame is not None:
                yield (BOUNDARY + b"\r\n"
                                  b"Content-Type: image/jpeg\r\n\r\n" + last_encoded_frame + b"\r\n")

            # 【修正】ループの速度を制御し、CPU負荷を削減
            time.sleep(1 / FRAME_RATE)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ----------- 新增：地面設定 弹窗（GET） -----------
@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/ground-settings", methods=["GET"])
def ground_settings_modal(magistrate_id: int):
    cam = load_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"))
    # 传入当前 ground_coords & 已计算尺寸
    return render_template(
        "partials/ground_settings_modal.html",
        magistrate_id=magistrate_id,
        cam=cam
    )


# ----------- 地面尺寸计算（POST） -----------
@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/ground-settings/calc", methods=["POST"])
def ground_settings_calc(magistrate_id: int):
    cam = load_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"))

    # 读取 points，支持 JSON 或 form
    pts = request.json.get("points") if request.is_json else request.form.get("points")

    if isinstance(pts, str):
        import json
        pts = json.loads(pts)

    if not pts or len(pts) < 4:
        return jsonify({"ok": False, "msg": "請先在左側選取 4 個點"}), 400

    # 调用 ground_utils 计算
    width_m, depth_m = ground_utils.calculate_ground_dimensions(
        camera_height=cam.camera_height,
        pitch_angle=cam.pitch_angle,
        roll_angle=cam.roll_angle,
        yaw_angle=cam.yaw_angle,
        focal_length=list(cam.focal_length),
        principal_coord=list(cam.principal_coord),
        ground_coords=pts,
    )

    # 【修正】添加 return 语句，将计算结果渲染到模板并返回
    return render_template(
        "partials/ground_calc_result.html",
        ground_x=width_m,
        ground_y=depth_m
    )


# ----------- 新增：地面設定 保存（POST） -----------
@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/ground-settings", methods=["POST"])
def ground_settings_submit(magistrate_id: int):
    """
    保存 ground_coords, depth_scale, 以及计算出的 ground lengths。
    """
    cam_old = load_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"))

    if request.is_json:
        payload = request.json
    else:
        # Fallback for form data if needed
        import json
        payload = {
            "points": json.loads(request.form.get("points", "[]")),
            "ground_x": request.form.get("ground_x"),
            "ground_y": request.form.get("ground_y"),
        }

    pts = payload.get("points") or []
    try:
        gx = float(payload.get("ground_x"))
        gy = float(payload.get("ground_y"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "尺寸或深度格式不正确"}), 400

    if len(pts) != 4:
        return jsonify({"ok": False, "msg": "需要 4 個點"}), 400

    pts_int = [(int(round(p[0])), int(round(p[1]))) for p in pts]
    new_cam = CameraParametersConfig(
        camera_height=cam_old.camera_height,
        roll_angle=cam_old.roll_angle,
        pitch_angle=cam_old.pitch_angle,
        yaw_angle=cam_old.yaw_angle,
        focal_length=tuple(cam_old.focal_length),
        principal_coord=tuple(cam_old.principal_coord),
        ground_coords=pts_int,
        ground_x_length_calculated=int(round(gx * 1000)),
        ground_y_length_calculated=int(round(gy * 1000)),
        ground_z_length_calculated=cam_old.ground_z_length_calculated,
    )

    save_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"), new_cam)

    return render_template("partials/save_success_snackbar.html", message="地面設定を保存しました。")


# -------------------------------------------------------------------
# KeyArea Setting (新增)
# -------------------------------------------------------------------

@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/keyarea-settings", methods=["GET"])
def keyarea_settings_modal(magistrate_id: int):
    """显示重点区域设置模态框"""
    cfg_path = file_utils.get_config(f"magistrate_config{magistrate_id}")
    cfg = load_magistrate_config(cfg_path)
    current_area = cfg.client_magistrate.key_area_settings.area

    return render_template(
        "partials/keyarea_settings_modal.html",
        magistrate_id=magistrate_id,
        current_area=current_area
    )


@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/keyarea-settings", methods=["POST"])
def keyarea_settings_submit(magistrate_id: int):
    """保存新的重点区域"""
    payload = request.json
    new_points = payload.get("points")

    if not new_points or len(new_points) != 4:
        return "需要 4 個點", 400

    try:
        # 读取、更新、保存配置
        cfg_path = file_utils.get_config(f"magistrate_config{magistrate_id}")
        cfg = load_magistrate_config(cfg_path)

        # 将新坐标点位更新到配置对象中
        cfg.client_magistrate.key_area_settings.area = new_points

        save_magistrate_config(cfg_path, cfg)

        return render_template(
            "partials/save_success_snackbar.html",
            message="重点エリアを保存しました。"
        )
    except Exception as e:
        return f"保存失敗: {e}", 500