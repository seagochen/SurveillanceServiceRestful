# app/routes/monitor.py
from flask import Blueprint, current_app
from app import utils

bp_monitor = Blueprint('monitor', __name__)

@bp_monitor.route('/get-magistrate-grid')
def get_magistrate_grid():
    html_parts = []
    try:
        pipeline_config = utils.get_config("pipeline_config", return_path=False)
        enabled_sources = pipeline_config.get("client_pipeline", {}).get("enable_sources", [])
    except FileNotFoundError:
        pipeline_config = {}
        enabled_sources = []
        html_parts.append("<p>Error: pipeline_config.yaml not found!</p>")

    receiver = current_app.config.get("hb_receiver")

    for i in range(1, 9):
        magistrate_name = f"pipeline_inference_{i}"
        magistrate_id = f"magistrate_client_{i}"

        alias = pipeline_config.get("client_pipeline", {}).get(magistrate_name, {}).get("alias", f"クライアント {i}")
        ip_address = pipeline_config.get("client_pipeline", {}).get(magistrate_name, {}).get("camera_config", {}).get("address", "N/A")
        display_text = f"{alias} - {ip_address}"

        if magistrate_name in enabled_sources and receiver:
            derived, _ = receiver.get_magistrate_status(magistrate_id)
            if derived == "online":
                status_class = 'status-enabled-online'
            elif derived == "stale":
                status_class = 'status-enabled-stale'
            else:
                status_class = 'status-enabled-offline'
        else:
            status_class = 'status-disabled'

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
        pipeline_config = utils.get_config("pipeline_config", return_path=False)
        client_id_to_check = pipeline_config.get("broker", {}).get("client_id", "pipeline_client")
    except FileNotFoundError:
        client_id_to_check = "pipeline_client"

    receiver = current_app.config.get("hb_receiver")
    derived = "offline"
    if receiver:
        derived, _ = receiver.get_pipeline_status(client_id_to_check)

    if derived == "online":
        dot_class, status_text = 'dot-green', '接続中'
    elif derived == "stale":
        dot_class, status_text = 'dot-yellow', '不明'
    else:
        dot_class, status_text = 'dot-red', '切断'

    return f"""
        <span class="label" style="font-size: 0.7em;">推論モジュール:</span>
        <span class="dot {dot_class}"></span>
        <span style="font-size: 0.7em;">{status_text}</span>
    """
