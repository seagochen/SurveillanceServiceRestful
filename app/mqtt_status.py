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


######################################################
# MQTT 状态消息处理函数
######################################################

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
    """
    启动一个后台线程来监听 MQTT 状态。
    在启动前，先清空历史保留消息。
    """
    try:
        # 【新增】清空保留消息
        pipeline_config = utils.get_config("pipeline_config")
        broker_host = pipeline_config.get("broker", {}).get("host", "localhost")
        broker_port = pipeline_config.get("broker", {}).get("port", 1883)
        topics_to_clear = ["pipelines/+/status", "magistrates/+/status"]
        utils.clear_retained_status_messages(broker_host, broker_port, topics_to_clear)

    except FileNotFoundError:
        print("警告: pipeline_config.yaml 未找到，使用默认 MQTT Broker 地址。")
        broker_host = "localhost"
        broker_port = 1883
        topics_to_clear = ["pipelines/+/status", "magistrates/+/status"]
        utils.clear_retained_status_messages(broker_host, broker_port, topics_to_clear)
    except Exception as e:
        print(f"清空保留消息时发生错误: {e}，将继续启动状态监控。")

    monitor_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "flask_monitor_client")
    monitor_client.on_message = on_status_message
    monitor_client.connect(broker_host, broker_port, 60)
    
    # 订阅两种服务的状态主题
    monitor_client.subscribe("pipelines/+/status")
    monitor_client.subscribe("magistrates/+/status")
    
    monitor_client.loop_start()
    print("MQTT Status Monitor started for Pipelines and Magistrates.")


######################################################
# Flask 路由处理函数
######################################################

@main_bp.route('/get-magistrate-grid')
def get_magistrate_grid():
    """
    生成包含8个 magistrate 状态按钮的 HTML 网格。
    现在会显示 alias - IP。
    """
    html_parts = []
    
    try:
        pipeline_config = utils.get_config("pipeline_config")
        enabled_sources = pipeline_config.get("client_pipeline", {}).get("enable_sources", [])
    except FileNotFoundError:
        enabled_sources = []
        html_parts.append("<p>Error: pipeline_config.yaml not found!</p>")
        pipeline_config = {} # Ensure pipeline_config is defined even if file not found

    with status_lock:
        for i in range(1, 9):
            magistrate_name = f"pipeline_inference_{i}"
            magistrate_id_str = f"magistrate_client_{i}" # Use a different variable name to avoid confusion with integer magistrate_id

            status_class = 'status-disabled' # 默认为灰色 (未启用)
            
            # 获取 alias 和 IP 地址
            alias = pipeline_config.get("client_pipeline", {}).get(magistrate_name, {}).get("alias", f"クライアント {i}")
            ip_address = pipeline_config.get("client_pipeline", {}).get(magistrate_name, {}).get("camera_config", {}).get("address", "N/A")
            display_text = f"{alias} - {ip_address}"

            # 循环检测每一个 magistrate 的状态
            if magistrate_name in enabled_sources:  # 如果该 magistrate 被启用
                magistrate_data = magistrate_statuses.get(magistrate_id_str)  # 使用 magistrate_id_str 获取状态数据
                
                # 检查状态并设置相应的样式
                if magistrate_data:
                    status_text = magistrate_data['status']  # 'online', 'offline', 'stale'
                    last_seen_ago = time.time() - magistrate_data.get('last_seen', 0)  # 计算最后一次看到的时间差

                    if status_text == 'online' and last_seen_ago <= 20: # 使用20秒作为stale阈值
                        status_class = 'status-enabled-online'
                    else:
                        status_class = 'status-enabled-offline'
                else:
                    status_class = 'status-enabled-offline'
            
            html_parts.append(f"""
                <div class="status-box {status_class}" 
                     style="cursor: pointer;"
                     hx-get="/panel/magistrate/{i}"
                     hx-target="#main-content"
                     hx-swap="innerHTML"
                     hx-push-url="true">
                    {display_text}
                </div>
            """)

    return "".join(html_parts)


@main_bp.route('/get-pipeline-indicator')
def get_pipeline_indicator():
    """【关键修改】返回 Pipeline 状态指示灯的 HTML 片段 (UTF-8 点状指示灯)。"""
    try:
        pipeline_config = utils.get_config("pipeline_config")
        client_id_to_check = pipeline_config.get("broker", {}).get("client_id", "pipeline_client")
    except FileNotFoundError:
        client_id_to_check = "pipeline_client"

    dot_class = 'dot-red'    # 默认为红色
    status_text = '切断'     # Disconnected

    with status_lock:
        pipeline_data = pipeline_statuses.get(client_id_to_check)
        if pipeline_data:
            last_seen_ago = time.time() - pipeline_data.get('last_seen', 0)
            if pipeline_data.get('status') == 'online' and last_seen_ago <= 20:
                dot_class = 'dot-green'  # 绿色
                status_text = '接続中'   # Connected
            elif pipeline_data.get('status') == 'online' and last_seen_ago > 20:
                dot_class = 'dot-yellow' # 黄色
                status_text = '不明'     # Stale/Unknown
    
    # 返回新的 HTML 片段，它将被注入到 #pipeline-status-indicator 内部
    return f"""
        <span class="label" style="font-size: 0.7em;">推論モジュール:</span>
        <span class="dot {dot_class}"></span>
        <span style="font-size: 0.7em;">{status_text}</span>
    """

def get_magistrate_status(magistrate_id: int) -> str:
    """获取指定 magistrate 客户端的当前状态 ('online', 'offline', 'stale')。"""
    client_id = f"magistrate_client_{magistrate_id}"
    with status_lock:
        data = magistrate_statuses.get(client_id)
        if not data:
            return "offline"
        
        status_text = data.get('status', 'offline')
        last_seen_ago = time.time() - data.get('last_seen', 0)

        if status_text == 'online' and last_seen_ago > 20: # stale 阈值
            return "stale"
        return status_text