# app/routes/monitor.py
from flask import Blueprint, current_app
from app import utils
from app.config.pipeline_config_parser import PipelineConfig, load_pipeline_config
from pyengine.io.network.plugins.heart_beat_receiver import HeartbeatReceiverPlugin, HeartbeatState

bp_monitor = Blueprint('monitor', __name__)

@bp_monitor.route('/get-magistrate-grid')
def get_magistrate_grid():
    html_parts = []

    # 获取YAML配置
    cfg_path = utils.get_config("pipeline_config")
    cfg: PipelineConfig = load_pipeline_config(cfg_path)

    # 获取心跳
    receiver = current_app.config.get("hb_receiver")

    for i in range(1, 9):
        magistrate_name = f"pipeline_inference_{i}"
        magistrate_id = f"magistrate_client_{i}"

        alias = cfg.client_pipeline.inferences[magistrate_name].alias
        ip_address = cfg.client_pipeline.inferences[magistrate_name].camera_config.address
        display_text = f"{alias} - {ip_address}"

        # 判断是否启动
        if magistrate_name in cfg.client_pipeline.enable_sources:
            state = receiver.get_state(f"magistrates/{magistrate_id}/status")
            if state == "online":
                status_class = 'status-enabled-online'
            elif state == "stale":
                status_class = 'status-enabled-stale'
            else:
                status_class = 'status-enabled-offline'
        else:
            status_class = 'status-disabled'

        # 组装消息
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

@bp_monitor.route('/get-pipeline-indicator')
def get_pipeline_indicator():
    try:
        # Get the YAML file
        cfg_path = utils.get_config("pipeline_config")
        cfg: PipelineConfig = load_pipeline_config(cfg_path)

        # Get the client id
        client_id_to_check = cfg.broker.client_id

    except FileNotFoundError:
        client_id_to_check = "pipeline_client"

    # 获取心跳
    receiver: HeartbeatReceiverPlugin = current_app.config.get("hb_receiver")

    # 解析状态
    if receiver:
        state = receiver.get_state(f"pipelines/{client_id_to_check}/status")
        if state == "online":
            dot_class, status_text = 'dot-green', '接続中'
        elif state == "stale":
            dot_class, status_text = 'dot-yellow', '不明'
        else:
            dot_class, status_text = 'dot-red', '切断'
    else:
        dot_class, status_text = 'dot-yellow', '不明'

    # 渲染消息
    return f"""
        <span class="label" style="font-size: 0.7em;">推論モジュール:</span>
        <span class="dot {dot_class}"></span>
        <span style="font-size: 0.7em;">{status_text}</span>
    """
