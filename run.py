import os
from app import create_app
from app import mqtt_status
from app.utils import synchronize_configs

app = create_app()


if __name__ == '__main__':

    # 同步配置文件
    synchronize_configs()

    # 2. 检查环境变量，确保只在主工作进程中启动监控
    #    这样可以避免在 Flask 的重载器监控进程中也启动一个实例
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        # --- 启动 MQTT 后台监控线程 ---
        mqtt_status.start_status_monitor()

    # 只运行一次 Flask 应用
    # debug=True 会自动在代码修改时重新加载应用
    app.run(debug=True, host='0.0.0.0', port=5000)