# app/routes/monitor.py
import time
import threading
from flask import Blueprint, current_app
from app.utils import file_utils
from pyengine.config.pipeline_config_parser import PipelineConfig, load_pipeline_config
from pyengine.io.network.plugins.heart_beat_receiver import HeartbeatReceiverPlugin

bp_monitor = Blueprint('monitor', __name__)

# --- 【新增】缓存和锁的初始化 ---
_config_cache = {}
_last_load_time = 0.0
_config_lock = threading.Lock()
CACHE_TIMEOUT = 10.0  # 缓存超时时间，10秒


def _get_cached_pipeline_config() -> PipelineConfig:
    """
    一个带超时机制的、线程安全的函数，用于获取 pipeline_config 配置。
    """
    global _last_load_time, _config_cache

    # 使用 'with' 语句自动管理锁的获取和释放
    with _config_lock:
        # 检查缓存是否超时
        if (time.time() - _last_load_time) > CACHE_TIMEOUT:
            try:
                print(f"[INFO] Monitor config cache expired. Reloading pipeline_config.yaml...")
                cfg_path = file_utils.get_config("pipeline_config")
                cfg = load_pipeline_config(cfg_path)

                # 更新缓存和时间戳
                _config_cache['pipeline'] = cfg
                _last_load_time = time.time()

            except Exception as e:
                print(f"[ERROR] Failed to reload pipeline_config.yaml: {e}")
                # 如果加载失败，继续使用旧的缓存（如果存在）
                if 'pipeline' not in _config_cache:
                    raise  # 如果连初始缓存都没有，则重新抛出异常

        return _config_cache['pipeline']


@bp_monitor.route('/get-magistrate-grid')
def get_magistrate_grid():
    html_parts = []

    # 【修改】从缓存中获取配置
    cfg: PipelineConfig = _get_cached_pipeline_config()

    # 获取心跳
    receiver: HeartbeatReceiverPlugin = current_app.config.get("hb_receiver")

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
        # 【修改】从缓存中获取配置
        cfg: PipelineConfig = _get_cached_pipeline_config()
        client_id_to_check = cfg.broker.client_id
    except Exception:
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