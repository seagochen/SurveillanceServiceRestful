import os
from typing import List, Dict, Any, Optional

import cv2

from pyengine.io.network.mqtt_bus import MqttBus
from pyengine.io.network.mqtt_plugins import MqttPluginManager
from pyengine.io.network.plugins.heart_beat_sender import HeartbeatSenderPlugin
from pyengine.io.network.protobufs import import_inference_result, import_rawframe

# ===== Configurable Parameters (can be overridden by environment variables) =====
BROKER_HOST = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
VID_PATH = os.getenv("VID_PATH", "/opt/videos/onsite_normal_test.mp4")
NUM_MAGISTRATES = 8  # Fixed number of magistrate clients to simulate


# ===== Heartbeat Client Wrapper =====
class SimClient:
    """A wrapper for a simulated client that handles its MQTT connection and heartbeat."""

    def __init__(self, client_id: str, status_topic: str):
        self.client_id = client_id
        self.status_topic = status_topic
        # Each client gets its own MQTT bus instance
        self.bus = MqttBus(host=BROKER_HOST, port=BROKER_PORT, client_id=client_id)
        # The heartbeat plugin sends 'online' status every 15s and 'offline' on stop
        self.hb = HeartbeatSenderPlugin(topic=status_topic, interval=15.0, retain=True, debug=False)
        # Use plugin manager to manage the plugins
        self.pm = MqttPluginManager(self.bus)

        # Flags
        self.is_active = False
        self._started = False

        # Add the plugins to the bus
        self.pm.register(self.hb)

    def connect(self):
        """Starts the underlying MQTT connection loop."""
        if not self._started:
            self.bus.start()
            self._started = True
        return True

    def start_heartbeat(self):
        """Activates the heartbeat, sending 'online' messages."""
        if not self.is_active:
            self.is_active = True
            # 启动插件管理器 → HeartbeatSenderPlugin.start(...) 线程才会运行
            self.pm.start()
            print(f"---> Client '{self.client_id}' is now ONLINE (topic={self.status_topic})")

    def stop_heartbeat(self):
        """Deactivates the heartbeat, sending a final 'offline' message."""
        if self.is_active:
            self.is_active = False
            # 停止插件 → 触发 HeartbeatSenderPlugin 在退出时发送 'offline'
            self.pm.stop()
            print(f"---> Client '{self.client_id}' is now OFFLINE")

    def disconnect(self):
        """Stops the heartbeat and disconnects the client completely."""
        try:
            if self.is_active:
                self.pm.stop()
        finally:
            if self._started:
                self.bus.stop()
                self._started = False


def make_inference_result_packer(pb2_dir: str,
                                 jpeg_quality: int = 85,
                                 publisher: str = "test",
                                 results_bytes_func: Optional[callable] = None):
    """
    返回 pack(frame, meta) -> bytes
    - 将 BGR 帧压成 JPEG，写入 InferenceResult.frame_raw_data
    - inference_results:
        * 如果 results_bytes_func 不为 None：用其返回的 bytes
        * 否则为空字节 b""
    - frame_number:
        * 优先 meta["frame_number"]；否则使用内部计数器自增
    """
    InferenceResult = import_inference_result(pb2_dir)  # 正确的类

    def pack(frame, meta: Dict[str, Any]) -> bytes:
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
        if not ok:
            raise RuntimeError("JPEG encode failed")
        h, w = frame.shape[:2]

        msg = InferenceResult()
        msg.frame_number    = 0
        msg.frame_width     = int(meta.get("width",  w))
        msg.frame_height    = int(meta.get("height", h))
        msg.frame_channels  = 3  # BGR
        msg.frame_raw_data  = buf.tobytes()
        msg.publish_by      = str(meta.get("publish_by", publisher))

        if results_bytes_func is not None:
            # 约定：results_bytes_func 返回“已序列化好的检测结果 bytes”
            # 例如：DetectionSet().SerializeToString()
            rb = results_bytes_func(frame, meta)
            if not isinstance(rb, (bytes, bytearray, memoryview)):
                raise TypeError("results_bytes_func must return bytes")
            msg.inference_results = bytes(rb)
        else:
            msg.inference_results = b""

        return msg.SerializeToString()

    return pack


def make_rawframe_packer(pb2_dir: str, jpeg_quality: int = 85):
    """
    如果你想用 RawFrame（raw_frames.proto）而不是 InferenceResult：
    - 只包含帧的宽高通道和 JPEG 字节。
    """
    RawFrame = import_rawframe(pb2_dir)

    def pack(frame, meta: Dict[str, Any]) -> bytes:
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
        if not ok:
            raise RuntimeError("JPEG encode failed")
        h, w = frame.shape[:2]

        msg = RawFrame()
        # 该 proto 有 frame_fps 字段；可从 meta 传，没有就置 0
        msg.frame_fps       = int(meta.get("fps", 0))
        msg.frame_width     = int(meta.get("width",  w))
        msg.frame_height    = int(meta.get("height", h))
        msg.frame_channels  = 3
        msg.frame_raw_data  = buf.tobytes()
        return msg.SerializeToString()

    return pack


# ===== Interactive Command-Line Interface =====
def print_status(pipeline_client: SimClient, mag_clients: List[SimClient]):
    """Prints the current status of all simulated clients to the console."""
    print("\n" + "=" * 50)
    print(" Fake Clients Simulator Status (Heartbeat Only)")
    print("-" * 50)
    # Print pipeline status
    pipeline_status = 'ONLINE' if pipeline_client.is_active else 'OFFLINE'
    print(f"  Pipeline ({pipeline_client.client_id}): {pipeline_status}")
    print("-" * 50)
    # Print magistrate statuses
    for i, c in enumerate(mag_clients, start=1):
        status = 'ONLINE' if c.is_active else 'OFFLINE'
        print(f"  Magistrate {i} ({c.client_id}): {status}")
    print("=" * 50)


def main():
    """Main function to run the interactive simulator."""
    print("=" * 50)
    print("Initializing fake clients...")

    # Initialize the pipeline client
    pipeline = SimClient("pipeline_client", "pipelines/pipeline_client/status")
    pipeline.connect()

    # Initialize magistrate clients 1 through 8
    mag_clients: List[SimClient] = []
    for i in range(1, NUM_MAGISTRATES + 1):
        cid = f"magistrate_client_{i}"
        topic = f"magistrates/{cid}/status"
        cli = SimClient(cid, topic)
        cli.connect()
        mag_clients.append(cli)

    try:
        # An instance to hold the user input
        user_input = None

        while True:
            print_status(pipeline, mag_clients)
            try:
                user_input = input(
                    "Enter command ('on'/'off' for pipeline, 1-8 for magistrates, 'q' to quit): ").lower().strip()
            except KeyboardInterrupt:
                break  # Exit on Ctrl+C

            if user_input == 'q':
                break
            elif user_input == 'on':
                if not pipeline.is_active:
                    pipeline.start_heartbeat()
                else:
                    print("[Info] Pipeline is already ON.")
            elif user_input == 'off':
                if pipeline.is_active:
                    pipeline.stop_heartbeat()
                else:
                    print("[Info] Pipeline is already OFF.")
            else:
                try:
                    k = int(user_input)
                    if 1 <= k <= NUM_MAGISTRATES:
                        client_to_toggle = mag_clients[k - 1]
                        if client_to_toggle.is_active:
                            client_to_toggle.stop_heartbeat()
                        else:
                            client_to_toggle.start_heartbeat()
                    else:
                        print(f"Invalid number. Please enter a number between 1 and {NUM_MAGISTRATES}.")
                except ValueError:
                    print("Invalid command. Please enter 'on', 'off', a number, or 'q'.")

    finally:
        print("\nCleaning up and disconnecting all clients...")
        # Disconnect all clients gracefully
        try:
            if pipeline.is_active: pipeline.stop_heartbeat()
            pipeline.disconnect()
        except Exception as e:
            print(f"Error disconnecting pipeline: {e}")

        for c in mag_clients:
            try:
                if c.is_active: c.stop_heartbeat()
                c.disconnect()
            except Exception as e:
                print(f"Error disconnecting {c.client_id}: {e}")

        print("All clients disconnected. Exiting.")


if __name__ == "__main__":
    main()