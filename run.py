import os

from app import create_app, utils
from pyengine.io.network.mqtt_bus import MqttBus
from pyengine.io.network.mqtt_plugins import MqttPluginManager
from pyengine.io.network.plugins.heart_beat_receiver import HeartbeatReceiverPlugin

app = create_app()


def _start_mqtt_receiver_and_inject(app):
    """启动 MQTT 总线与心跳接收插件，并把插件实例放进 Flask app.config。"""
    # 从 pipeline_config 读取 broker 配置（容错）
    host, port, client_id = "127.0.0.1", 1883, "status_dashboard"

    # 启动总线
    bus = MqttBus(host=host, port=port, client_id=client_id)
    bus.start()

    # 注册插件
    pm = MqttPluginManager(bus)
    receiver = HeartbeatReceiverPlugin(topics=["pipelines/+/status", "magistrates/+/status"], timeout_sec=20, debug=False)
    pm.register(receiver)

    # 启动插件
    pm.start()

    # 注入到 Flask（路由用 current_app.config["hb_receiver"] 访问）
    app.config["mqtt_bus"] = bus
    app.config["hb_receiver"] = receiver

    return bus, receiver


def _stop_mqtt_receiver(bus, receiver):
    """退出时优雅关闭插件与总线。"""
    try:
        if receiver:
            receiver.stop()
    finally:
        if bus:
            bus.stop()


if __name__ == '__main__':

    # 1) 同步配置
    utils.copy_configs(src_folder="/opt/SurveillanceService/configs",
                       dest_folder="/opt/SurveillanceServiceRestful/configs")

    # 2) 仅在主工作进程里启动 MQTT（避免 Flask reloader 启两份）
    bus = receiver = None
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        bus, receiver = _start_mqtt_receiver_and_inject(app)

    try:
        # 3) 启动 Flask
        app.run(debug=True, host='0.0.0.0', port=5000)
    finally:
        _stop_mqtt_receiver(bus, receiver)