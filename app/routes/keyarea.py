# app/routes/keyarea.py
import cv2
import numpy as np
import time
from flask import Blueprint, render_template, Response, current_app, request, jsonify
from app.utils import file_utils, ground_utils
from pyengine.config.camera_setting_parser import load_camera_settings, CameraParametersConfig, save_camera_settings
from pyengine.config.pipeline_config_parser import PipelineConfig, load_pipeline_config
from pyengine.config.magistrate_config_parser import MagistrateConfig, load_magistrate_config
from pyengine.io.network.plugins.inference_result_receiver import InferenceResultReceiverPlugin
from pyengine.utils import scale_utils
from pyengine.visualization import polygon_drawer

bp_keyarea = Blueprint("keyarea", __name__)


#------------------------------------------------------------------
# MQTT Display
#------------------------------------------------------------------

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

@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>")
def keyarea_panel(magistrate_id: int):
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

@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/frame")
def keyarea_frame(magistrate_id: int):
    """
    通过 MQTT 订阅器读取最新一帧，转成 MJPEG 推到前端。
    订阅器实例在 run.py 启动时已注入 app.config（见 run.py）。
    """
    
    # 从 Application Context 获取 mqtt receiver
    topic_key = f"pipeline_inference_{magistrate_id}"
    receiver: InferenceResultReceiverPlugin = current_app.config.get(f"inference_{magistrate_id}")
    if receiver is None:
        return f"MQTT receiver not found for {topic_key}", 404
    
    # 显示画面使用 640 x 480
    TARGET_W, TARGET_H = 640, 480
    BOUNDARY = b"--frame"
    
    # 从配置文件中读取检测区域
    cfg: MagistrateConfig = load_magistrate_config(file_utils.get_config(f"magistrate_config{magistrate_id}"))
    key_area = cfg.client_magistrate.key_area_settings.area
    key_color = cfg.client_magistrate.key_area_settings.color
    key_alpha = cfg.client_magistrate.key_area_settings.alpha

    # 对配置区域进行缩放
    key_area = scale_utils.scale_euler_pts(
        src_width=800,
        src_height=600,
        dst_width=640,
        dst_height=480,
        points=key_area
    )

    # 生成显示画面
    def generate():
        # 若长时间没有新数据，也保持连接，发一张占位图降低闪烁
        blank = np.zeros((TARGET_H, TARGET_W, 3), dtype=np.uint8)
        last_send_ts = 0.0

        while True:
            msg = receiver.read()  # 直接得到 protobuf（参见 inference_result_receiver.py 的 read()）  :contentReference[oaicite:3]{index=3}
            frame = _pb_to_ndarray(msg) if msg is not None else None

            if frame is not None:
                # MQTT 过来的多为 RGB/BGR，保持一致后统一缩放到 800x600
                if frame.ndim == 2:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else:
                    # 假定为 BGR；若上游是 RGB，可在此处 cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    frame_bgr = frame
                frame_bgr = cv2.resize(frame_bgr, (TARGET_W, TARGET_H))
            else:
                # 没有新帧：隔 0.5s 发送一次占位，保持 MJPEG 连接活跃
                if time.time() - last_send_ts < 0.5:
                    time.sleep(0.02)
                    continue
                frame_bgr = blank

            # 绘制检测区域
            frame_bgr = polygon_drawer.fill_area(frame_bgr, key_area, key_color, key_alpha)

            ok, buf = cv2.imencode(".jpg", frame_bgr)
            if not ok:
                continue

            last_send_ts = time.time()
            yield (
                BOUNDARY + b"\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                buf.tobytes() + b"\r\n"
            )

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


#-------------------------------------------------------------------
# Camera Setting
#-------------------------------------------------------------------

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
        depth_scale=old.depth_scale,  # MODIFIED: depth_scale 不再从此表单提交，直接沿用旧值
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

#-------------------------------------------------------------------
# Ground Setting
#-------------------------------------------------------------------

# ----------- 新增：800x600 的帧流（供地面設定弹窗左侧使用） -----------
@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/frame800")
def keyarea_frame_800(magistrate_id: int):
    receiver: InferenceResultReceiverPlugin = current_app.config.get(f"inference_{magistrate_id}")
    if receiver is None:
        return f"MQTT receiver not found for pipeline_inference_{magistrate_id}", 404

    TARGET_W, TARGET_H = 800, 600
    BOUNDARY = b"--frame"

    # 取当前重点区域涂色（可与主界面一致）
    cfg: MagistrateConfig = load_magistrate_config(file_utils.get_config(f"magistrate_config{magistrate_id}"))
    key_area = cfg.client_magistrate.key_area_settings.area
    key_color = cfg.client_magistrate.key_area_settings.color
    key_alpha = cfg.client_magistrate.key_area_settings.alpha

    def generate():
        blank = np.zeros((TARGET_H, TARGET_W, 3), dtype=np.uint8)
        last_send_ts = 0.0
        while True:
            msg = receiver.read()
            frame = _pb_to_ndarray(msg) if msg is not None else None

            if frame is not None:
                if frame.ndim == 2:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else:
                    frame_bgr = frame
                frame_bgr = cv2.resize(frame_bgr, (TARGET_W, TARGET_H))
            else:
                if time.time() - last_send_ts < 0.5:
                    time.sleep(0.02)
                    continue
                frame_bgr = blank

            # 可选：绘制当前重点区域
            if key_area:
                frame_bgr = polygon_drawer.fill_area(frame_bgr, key_area, key_color, key_alpha)

            ok, buf = cv2.imencode(".jpg", frame_bgr)
            if not ok:
                continue
            last_send_ts = time.time()
            yield (BOUNDARY + b"\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

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


# ----------- 新增：地面尺寸计算（POST） -----------
# ----------- 地面尺寸计算（POST） -----------
@bp_keyarea.route("/panel/keyarea/<int:magistrate_id>/ground-settings/calc", methods=["POST"])
def ground_settings_calc(magistrate_id: int):
    cam = load_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"))

    # 读取 points，支持 JSON 或 form
    pts = request.json.get("points") if request.is_json else request.form.get("points")
    depth_scale_req = None
    if request.is_json:
        depth_scale_req = request.json.get("depth_scale")
    else:
        depth_scale_req = request.form.get("depth_scale")
    try:
        depth_scale = float(depth_scale_req) if depth_scale_req is not None else float(cam.depth_scale)
    except Exception:
        depth_scale = float(cam.depth_scale)

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
        depth_scale=depth_scale
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
            "depth_scale": request.form.get("depth_scale"),
        }

    pts = payload.get("points") or []
    try:
        gx = float(payload.get("ground_x"))
        gy = float(payload.get("ground_y"))
        # MODIFIED: 从 payload 中读取 depth_scale
        depth_scale = float(payload.get("depth_scale", cam_old.depth_scale))
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
        depth_scale=depth_scale,  # MODIFIED: 保存新的 depth_scale
        ground_x_length_calculated=int(round(gx * 1000)),
        ground_y_length_calculated=int(round(gy * 1000)),
        ground_z_length_calculated=cam_old.ground_z_length_calculated,
    )

    save_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"), new_cam)

    return render_template("partials/save_success_snackbar.html", message="地面設定を保存しました。")