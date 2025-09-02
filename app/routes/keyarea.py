# app/routes/keyarea.py
import cv2
import numpy as np
import time
from flask import Blueprint, render_template, Response, current_app, request
from app.utils import file_utils
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
        ground_coords=old.ground_coords,  # 表单未编辑，沿用
        depth_scale=_get_float("depth_scale", old.depth_scale),
        ground_x_length_calculated=old.ground_x_length_calculated,
        ground_y_length_calculated=old.ground_y_length_calculated,
        ground_z_length_calculated=old.ground_z_length_calculated,
    )

    save_camera_settings(file_utils.get_config(f"camera_parameters{magistrate_id}"), new_cfg)

    # 返回一个小的成功提示片段（HTMX 直接替换当前 modal 内容）
    return render_template(
        "partials/save_success_snackbar.html",
        message="カメラパラメータを保存しました。"
    )