import paho.mqtt.client as mqtt
import threading
import time
import json
import sys

# --- 全局配置 ---
BROKER_HOST = "localhost"
BROKER_PORT = 1883
NUM_MAGISTRATES = 8
HEARTBEAT_INTERVAL = 1  # seconds
PIPELINE_CLIENT_ID = "pipeline_client"


class FakeClient:
    """一个通用的模拟客户端基类，处理连接和心跳。"""

    def __init__(self, client_id: str, status_topic: str):
        self.client_id = client_id
        self.status_topic = status_topic
        self.is_active = False
        self.heartbeat_thread = None

        # 创建 Paho MQTT 客户端实例
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, self.client_id)

        # 设置遗嘱消息 (LWT)
        offline_payload = json.dumps({"timestamp": time.time(), "status": "offline"})
        self.client.will_set(self.status_topic, payload=offline_payload, qos=1, retain=True)

    def connect(self):
        """连接到 Broker"""
        try:
            self.client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.client.loop_start()
            print(f"  - Client '{self.client_id}' connected.")
            return True
        except Exception as e:
            print(f"  - Client '{self.client_id}' FAILED to connect: {e}")
            return False

    def start(self):
        """启动心跳并发布 'online' 状态"""
        if not self.is_active:
            self.is_active = True
            print(f"\n---> Client '{self.client_id}' is now ONLINE.")

            online_payload = json.dumps({"timestamp": time.time(), "status": "online"})
            self.client.publish(self.status_topic, payload=online_payload, qos=1, retain=True)

            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()

    def stop(self):
        """停止心跳并发布 'offline' 状态"""
        if self.is_active:
            self.is_active = False
            print(f"\n---> Client '{self.client_id}' is now OFFLINE.")

            offline_payload = json.dumps({"timestamp": time.time(), "status": "offline"})
            self.client.publish(self.status_topic, payload=offline_payload, qos=1, retain=True)

            if self.heartbeat_thread:
                self.heartbeat_thread.join()

    def _heartbeat_loop(self):
        """在后台线程中循环发送心跳"""
        while self.is_active:
            payload = json.dumps({"timestamp": time.time(), "status": "online"})
            self.client.publish(self.status_topic, payload=payload, qos=1, retain=True)
            time.sleep(HEARTBEAT_INTERVAL)

    def disconnect(self):
        """断开连接"""
        self.client.loop_stop()
        self.client.disconnect()


def print_status(pipeline_client, magistrate_clients):
    """打印所有客户端的当前状态"""
    print("\n" + "=" * 50)
    print(" Unified Clients Simulator Status")
    print("-" * 50)

    # 打印 Pipeline 状态
    pipeline_status = "ONLINE" if pipeline_client.is_active else "OFFLINE"
    print(f"  Pipeline ({pipeline_client.client_id}): {pipeline_status}")
    print("-" * 50)

    # 打印 Magistrate 状态
    for i, client in enumerate(magistrate_clients):
        status = "ONLINE" if client.is_active else "OFFLINE"
        print(f"  Magistrate {i + 1} ({client.client_id}): {status}")

    print("=" * 50)


def main():
    print("Initializing all fake clients...")

    # 初始化 Pipeline 客户端
    pipeline_client = FakeClient(PIPELINE_CLIENT_ID, f"pipelines/{PIPELINE_CLIENT_ID}/status")
    if not pipeline_client.connect():
        print("\nCould not connect pipeline client. Exiting.")
        sys.exit(1)

    # 初始化 Magistrate 客户端
    magistrate_clients = []
    for i in range(1, NUM_MAGISTRATES + 1):
        client_id = f"magistrate_client_{i}"
        status_topic = f"magistrates/{client_id}/status"
        client = FakeClient(client_id, status_topic)
        if client.connect():
            magistrate_clients.append(client)

    try:
        while True:
            print_status(pipeline_client, magistrate_clients)
            try:
                user_input = input("Enter command ('on'/'off', 1-8) or 'q' to quit: ").lower()

                if user_input == 'q':
                    break

                elif user_input == 'on':
                    pipeline_client.start()

                elif user_input == 'off':
                    pipeline_client.stop()

                else:
                    try:
                        client_num_to_toggle = int(user_input)
                        if 1 <= client_num_to_toggle <= len(magistrate_clients):
                            client = magistrate_clients[client_num_to_toggle - 1]
                            if client.is_active:
                                client.stop()
                            else:
                                client.start()
                        else:
                            print(f"Invalid number. Please enter a number between 1 and {NUM_MAGISTRATES}.")
                    except ValueError:
                        print("Invalid command. Please enter 'on', 'off', a number, or 'q'.")

            except KeyboardInterrupt:
                break

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Shutting down...")
    finally:
        print("\nCleaning up and disconnecting all clients...")
        # 清理 Pipeline
        if pipeline_client.is_active:
            pipeline_client.stop()
        pipeline_client.disconnect()

        # 清理 Magistrates
        for client in magistrate_clients:
            if client.is_active:
                client.stop()
            client.disconnect()

        print("All clients disconnected. Exiting.")


if __name__ == "__main__":
    main()