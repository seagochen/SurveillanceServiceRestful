# app/routes/keyarea.py
import cv2
import numpy as np
import time
from flask import Blueprint, render_template, Response, current_app
from app import utils
from app.config.pipeline_config_parser import load_pipeline_config
from pyengine.io.network.plugins.inference_result_receiver import InferenceResultReceiverPlugin

bp_keyarea = Blueprint("keyarea", __name__)

# ---- 小工具：把 MQTT 的 protobuf 里携带的裸像素还原成 np.ndarray ----
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
    cfg = load_pipeline_config(utils.get_config("pipeline_config"))
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
    topic_key = f"pipeline_inference_{magistrate_id}"
    receiver: InferenceResultReceiverPlugin = current_app.config.get(f"inference_{magistrate_id}")
    if receiver is None:
        return f"MQTT receiver not found for {topic_key}", 404

    TARGET_W, TARGET_H = 640, 480
    BOUNDARY = b"--frame"

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
