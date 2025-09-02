import cv2
import time
import numpy as np
from pyengine.io.network.mqtt_bus import MqttBus
from pyengine.io.network.mqtt_plugins import MqttPluginManager
from pyengine.io.network.plugins.inference_result_receiver import InferenceResultReceiverPlugin

def try_recover_frame(msg):
    # 读取元信息
    w = int(getattr(msg, "frame_width", 0))
    h = int(getattr(msg, "frame_height", 0))
    c = int(getattr(msg, "frame_channels", 0))
    raw = bytes(getattr(msg, "frame_raw_data", b""))

    if not raw or w <= 0 or h <= 0:
        return None

    arr = np.frombuffer(raw, dtype=np.uint8)

    # 1) 先试“原始像素”
    # 若 c==0，按 size 猜测通道
    cand_channels = [c] if c in (1, 3) else []
    if not cand_channels:
        if arr.size == h * w: cand_channels = [1]
        elif arr.size == h * w * 3: cand_channels = [3]

    for cc in cand_channels:
        if cc == 1 and arr.size == h * w:
            return arr.reshape((h, w))
        if cc == 3 and arr.size == h * w * 3:
            return arr.reshape((h, w, 3))

    # 2) 再试“JPEG 压缩”
    img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is not None:
        return img

    # 3) 兜底：长度能整除也尝试 reshape
    if c > 0 and arr.size == h * w * c:
        try:
            return arr.reshape((h, w, c))
        except Exception:
            pass

    return None

def main():
    topic = "pipeline_inference_1"  # 改成你要测的 topic
    bus = MqttBus(host="127.0.0.1", port=1883, client_id="test_receiver")
    pm = MqttPluginManager(bus)
    receiver = InferenceResultReceiverPlugin(topic=topic)

    pm.register(receiver)
    bus.start()
    pm.start()
    print(f"Subscribed to {topic}")

    try:
        while True:
            msg = receiver.read()
            if msg is None:
                time.sleep(0.02)
                continue

            frame = try_recover_frame(msg)
            if frame is None:
                print("warn: cannot recover frame from payload")
                continue

            if frame.ndim == 2:
                show = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            else:
                show = frame
            cv2.imshow("recv", show)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        pm.stop()
        bus.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
