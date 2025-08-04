import paho.mqtt.client as mqtt
import threading
import json
import time

# 从同级目录的 routes.py 导入 main_bp
from .routes import main_bp
from . import utils

# --- 全局状态存储 ---
pipeline_statuses = {}
magistrate_statuses = {}
status_lock = threading.Lock() # 一个锁管理两个字典足够


def on_status_message(client, userdata, msg):
    """处理接收到的状态消息的回调函数"""
    try:
        parts = msg.topic.split('/')
        if len(parts) != 3 or parts[2] != 'status':
            return

        service_type = parts[0] # "pipelines" 或 "magistrates"
        client_id = parts[1]
        data = json.loads(msg.payload.decode('utf-8'))
        
        # 构建要存储的数据
        status_data = {
            "status": data.get("status", "unknown"),
            "last_seen": time.time(),
            "reported_at": data.get("timestamp", 0)
        }

        with status_lock:
            if service_type == 'pipelines':
                pipeline_statuses[client_id] = status_data
            elif service_type == 'magistrates':
                magistrate_statuses[client_id] = status_data

    except Exception as e:
        print(f"Error processing status message on topic {msg.topic}: {e}")


def start_status_monitor():
    """启动一个后台线程来监听 MQTT 状态"""
    monitor_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "flask_monitor_client")
    monitor_client.on_message = on_status_message
    monitor_client.connect("localhost", 1883, 60)
    
    # 订阅两种服务的状态主题
    monitor_client.subscribe("pipelines/+/status")
    monitor_client.subscribe("magistrates/+/status")
    
    monitor_client.loop_start()
    print("MQTT Status Monitor started for Pipelines and Magistrates.")


@main_bp.route('/get-magistrate-grid')
def get_magistrate_grid():
    """
    生成包含8个 magistrate 状态按钮的 HTML 网格。
    """
    html_parts = []
    
    try:
        pipeline_config = utils.get_config("pipeline_config")
        enabled_sources = pipeline_config.get("client_pipeline", {}).get("enable_sources", [])
    except FileNotFoundError:
        enabled_sources = []
        html_parts.append("<p>Error: pipeline_config.yaml not found!</p>")

    with status_lock:
        for i in range(1, 9):
            magistrate_name = f"pipeline_inference_{i}"
            magistrate_id = f"magistrate_client_{i}"

            # print(magistrate_name, "---->", magistrate_id)
            status_class = 'status-disabled' # 默认为灰色 (未启用)
            
            if magistrate_name in enabled_sources:
                magistrate_data = magistrate_statuses.get(magistrate_id)
                # print(magistrate_statuses)
                if magistrate_data:
                    status_text = magistrate_data['status']
                    last_seen_ago = time.time() - magistrate_data.get('last_seen', 0)
                    if status_text == 'online' and last_seen_ago <= 20: # 使用20秒作为stale阈值
                        status_class = 'status-enabled-online'
                    else:
                        status_class = 'status-enabled-offline'
                else:
                    status_class = 'status-enabled-offline'
            
            # --- 【关键修改】为 div 添加 htmx 点击事件 ---
            html_parts.append(f"""
                <div class="status-box {status_class}" 
                     style="cursor: pointer;"
                     hx-get="/panel/magistrate/{i}"
                     hx-target="#main-content"
                     hx-swap="innerHTML"
                     hx-push-url="true">
                    クライアント {i}
                </div>
            """)

    return "".join(html_parts)

