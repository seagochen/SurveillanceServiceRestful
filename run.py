import os

from app import create_app, utils
from pyengine.io.network.mqtt_bus import MqttBus
from pyengine.io.network.mqtt_plugins import MqttPluginManager
from pyengine.io.network.plugins.heart_beat_receiver import HeartbeatReceiverPlugin
from pyengine.io.network.plugins.inference_result_receiver import InferenceResultReceiverPlugin

app = create_app()

def _start_mqtt_receiver_and_inject(app):
    """启动 MQTT 总线与心跳接收插件，并把插件实例放进 Flask app.config。"""

    # 获取当前的进程ID
    current_pid = os.getpid()

    # 从 pipeline_config 读取 broker 配置（容错）
    host = "127.0.0.1"
    port = 1883
    # client_id = f"status_dashboard_{current_pid}"  # 测试用ID
    client_id = "status_dashboard"

    # 启动总线
    bus = MqttBus(host=host, port=port, client_id=client_id)
    bus.start()

    # 注册插件
    pm = MqttPluginManager(bus)
    receiver = HeartbeatReceiverPlugin(topics=["pipelines/+/status", "magistrates/+/status"], timeout_sec=20, debug=False)
    inference1 = InferenceResultReceiverPlugin(topic="pipeline_inference_1")
    inference2 = InferenceResultReceiverPlugin(topic="pipeline_inference_2")
    inference3 = InferenceResultReceiverPlugin(topic="pipeline_inference_3")
    inference4 = InferenceResultReceiverPlugin(topic="pipeline_inference_4")
    inference5 = InferenceResultReceiverPlugin(topic="pipeline_inference_5")
    inference6 = InferenceResultReceiverPlugin(topic="pipeline_inference_6")
    inference7 = InferenceResultReceiverPlugin(topic="pipeline_inference_7")
    inference8 = InferenceResultReceiverPlugin(topic="pipeline_inference_8")

    pm.register(receiver)
    pm.register(inference1)
    pm.register(inference2)
    pm.register(inference3)
    pm.register(inference4)
    pm.register(inference5)
    pm.register(inference6)
    pm.register(inference7)
    pm.register(inference8)

    # 启动插件
    pm.start()

    # 注入到 Flask（路由用 current_app.config["hb_receiver"] 访问）
    app.config["mqtt_bus"] = bus
    app.config["hb_receiver"] = receiver
    app.config["inference_1"] = inference1
    app.config["inference_2"] = inference2
    app.config["inference_3"] = inference3
    app.config["inference_4"] = inference4
    app.config["inference_5"] = inference5
    app.config["inference_6"] = inference6
    app.config["inference_7"] = inference7
    app.config["inference_8"] = inference8

    return bus, pm


def _stop_mqtt_service(bus, pm):
    """退出时优雅关闭插件与总线。"""
    try:
        if pm:
            pm.stop()
    finally:
        if bus:
            bus.stop()


if __name__ == '__main__':

    bus = pm = None
    try:

        # 拷贝文件
        # utils.copy_configs(src_folder="/opt/SurveillanceService/configs",
        #                    dest_folder="/opt/SurveillanceServiceRestful/configs")

        utils.copy_configs(
            src_folder="/opt/SurveillanceService/configs",
            dest_folder="/opt/SurveillanceServiceRestful/configs",
            default_folder="/opt/SurveillanceServiceRestful/configs_default",
            overwrite=False,   # 不覆盖
        )

        # 只在真正的工作进程里启动 MQTT（避免重复连接）
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':   # 子进程
            bus, pm = _start_mqtt_receiver_and_inject(app)

        # 设置 use_reloader=False 时，可以关闭 reloader
        app.run(debug=True, host='0.0.0.0', port=5000)      # reloader 依旧开启
    finally:
        _stop_mqtt_service(bus, pm)