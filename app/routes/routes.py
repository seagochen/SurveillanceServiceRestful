import json
import os

from flask import Blueprint, make_response, render_template, request

from app import utils

# 新增：引入解析器
from app.config.pipeline_config_parser import load_pipeline_config          # :contentReference[oaicite:3]{index=3}
from app.config.magistrate_config_parser import load_magistrate_config      # :contentReference[oaicite:4]{index=4}


# 创建一个蓝图实例
main_bp = Blueprint('main', __name__)


# --- Magistrate 面板路由 ---

@main_bp.route('/panel/magistrate/<int:magistrate_id>')
def magistrate_panel(magistrate_id: int):
    """
    从 pipeline_config 读取面板抬头信息（alias 与 IP）
    """
    try:
        cfg = load_pipeline_config(utils.get_config("pipeline_config"))   # 见下方小工具：用 dict 构建模型
        name = f"pipeline_inference_{magistrate_id}"

        inf = cfg.client_pipeline.inferences.get(name)   # 模型中的 inferences 字典  :contentReference[oaicite:5]{index=5}
        if not inf:
            return f"Error: '{name}' not found in pipeline_config.yaml", 404

        alias = getattr(inf, "camera_config", None) and getattr(inf, "camera_config").address
        alias = getattr(inf, "url", None)  # 若你 alias 存在别处可自行调整；这里只给示范位
        alias = inf.__dict__.get("alias", f"クライアント {magistrate_id}")  # 若模型中未定义 alias，可从 raw 兜底
        ip_address = (inf.camera_config.address if inf.camera_config else "N/A")

        return render_template('panel.html', magistrate_id=magistrate_id,
                               alias=alias, ip_address=ip_address)
    except Exception as e:
        return f"Error loading panel for magistrate {magistrate_id}: {e}", 500


@main_bp.route('/panel/magistrate/<int:magistrate_id>/toggle_button', methods=['GET'])
def get_toggle_button(magistrate_id: int):
    """
    基于 enable_sources 计算按钮状态（Pydantic 模型）
    """
    try:
        cfg = load_pipeline_config(utils.get_config("pipeline_config"))
        name = f"pipeline_inference_{magistrate_id}"
        is_enabled = name in cfg.client_pipeline.enable_sources
        return render_template('_toggle_button.html', magistrate_id=magistrate_id, is_enabled=is_enabled)
    except Exception as e:
        return f"<button disabled>Error: {e}</button>"


@main_bp.route('/panel/magistrate/<int:magistrate_id>/start_source', methods=['POST'])
def start_source(magistrate_id):
    """
    处理启用数据源的逻辑：修改 pipeline_config.yaml。
    """
    config_name = "pipeline_config"
    source_name = f"pipeline_inference_{magistrate_id}"
    try:
        config = utils.get_config(config_name)

        # 确保列表存在
        if "enable_sources" not in config["client_pipeline"]:
            config["client_pipeline"]["enable_sources"] = []
        if "disable_sources" not in config["client_pipeline"]:
            config["client_pipeline"]["disable_sources"] = []

        # 从 disable_sources 中移除 (如果存在)
        if source_name in config["client_pipeline"]["disable_sources"]:
            config["client_pipeline"]["disable_sources"].remove(source_name)

        # 添加到 enable_sources 中 (如果不存在)
        if source_name not in config["client_pipeline"]["enable_sources"]:
            config["client_pipeline"]["enable_sources"].append(source_name)

        utils.save_config(config_name, config)

        # 操作完成后，返回更新后的按钮状态
        return render_template(
            '_toggle_button.html',
            magistrate_id=magistrate_id,
            is_enabled=True
        )
    except Exception as e:
        return f"<button disabled>Error: {e}</button>"


@main_bp.route('/panel/magistrate/<int:magistrate_id>/stop_source', methods=['POST'])
def stop_source(magistrate_id):
    """
    处理禁用数据源的逻辑：修改 pipeline_config.yaml。
    """
    config_name = "pipeline_config"
    source_name = f"pipeline_inference_{magistrate_id}"
    try:
        config = utils.get_config(config_name)

        # 确保列表存在
        if "enable_sources" not in config["client_pipeline"]:
            config["client_pipeline"]["enable_sources"] = []
        if "disable_sources" not in config["client_pipeline"]:
            config["client_pipeline"]["disable_sources"] = []

        # 从 enable_sources 中移除 (如果存在)
        if source_name in config["client_pipeline"]["enable_sources"]:
            config["client_pipeline"]["enable_sources"].remove(source_name)

        # 添加到 disable_sources 中 (如果不存在)
        if source_name not in config["client_pipeline"]["disable_sources"]:
            config["client_pipeline"]["disable_sources"].append(source_name)

        utils.save_config(config_name, config)

        # 操作完成后，返回更新后的按钮状态
        return render_template(
            '_toggle_button.html',
            magistrate_id=magistrate_id,
            is_enabled=False
        )
    except Exception as e:
        return f"<button disabled>Error: {e}</button>"


# --- 摄像头配置面板 ---

@main_bp.route('/panel/camera/<int:magistrate_id>', methods=['GET'])
def get_camera_config_panel(magistrate_id):
    try:
        config_name = f"magistrate_config{magistrate_id}"
        magistrate_config = utils.get_config(config_name)
        inference_name = f"pipeline_inference_{magistrate_id}"
        cam_config = {
            "alias": magistrate_config["client_pipeline"][inference_name].get("alias", f"クライアント {magistrate_id}"),
            "camera_id": magistrate_config["client_pipeline"][inference_name]["camera_config"].get("camera_id", ""),
            "address": magistrate_config["client_pipeline"][inference_name]["camera_config"].get("address", ""),
            "port": magistrate_config["client_pipeline"][inference_name]["camera_config"].get("port", 554),
            "path": magistrate_config["client_pipeline"][inference_name]["camera_config"].get("path", ""),
            "username": magistrate_config["client_pipeline"][inference_name]["camera_config"].get("username", ""),
            "password": magistrate_config["client_pipeline"][inference_name]["camera_config"].get("password", ""),
        }
        return render_template('camera_config_panel.html', magistrate_id=magistrate_id, config=cam_config)
    except (FileNotFoundError, KeyError) as e:
        return f"Error loading camera config for magistrate {magistrate_id}: {e}", 404


@main_bp.route('/panel/camera/<int:magistrate_id>', methods=['POST'])
def update_camera_config_panel(magistrate_id):
    """
    更新相机配置，保存到本地，然后同步到生产环境，并触发弹窗跳转。
    """
    config_name = f"magistrate_config{magistrate_id}"
    inference_name = f"pipeline_inference_{magistrate_id}"
    try:
        config_data = utils.get_config(config_name)
        form_data = request.form

        # Update alias field
        config_data["client_pipeline"][inference_name]["alias"] = form_data.get("alias")

        cam_config_path = config_data["client_pipeline"][inference_name]["camera_config"]
        cam_config_path["camera_id"] = form_data.get("camera_id")
        cam_config_path["address"] = form_data.get("address")
        cam_config_path["port"] = int(form_data.get("port"))
        cam_config_path["path"] = form_data.get("path")
        cam_config_path["username"] = form_data.get("username")
        cam_config_path["password"] = form_data.get("password")

        utils.save_config(config_name, config_data)
        utils.sync_single_config(config_name)

        # 重新获取更新后的 alias 和 ip_address，并传给 panel.html
        updated_pipeline_config = utils.get_config("pipeline_config")
        updated_inference_details = updated_pipeline_config["client_pipeline"][inference_name]
        updated_alias = updated_inference_details.get('alias', f"クライアント {magistrate_id}")
        updated_ip_address = updated_inference_details.get('camera_config', {}).get("address", "N/A")

        html = render_template('panel.html', magistrate_id=magistrate_id, alias=updated_alias, ip_address=updated_ip_address)
        resp = make_response(html)
        # 关键：发出 HX-Trigger，让前端弹窗并在 2 秒后返回首页
        resp.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": "カメラ設定を保存しました"})
        return resp

    except (FileNotFoundError, KeyError, ValueError) as e:
        return f"Error updating camera config for magistrate {magistrate_id}: {e}", 500


# --- 云配置面板路由 ---

@main_bp.route('/panel/cloud/<int:magistrate_id>', methods=['GET'])
def get_cloud_config_panel(magistrate_id):
    """显示指定 magistrate_id 的云配置面板。"""
    try:
        config_name = f"magistrate_config{magistrate_id}"
        magistrate_config = utils.get_config(config_name)
        cloud_config = magistrate_config["client_magistrate"]["cloud"]
        return render_template('cloud_config_panel.html', magistrate_id=magistrate_id, config=cloud_config)
    except (FileNotFoundError, KeyError) as e:
        return f"Error loading cloud config for magistrate {magistrate_id}: {e}", 404


@main_bp.route('/panel/cloud/<int:magistrate_id>', methods=['POST'])
def update_cloud_config_panel(magistrate_id):
    """
    更新云配置，保存到本地，然后同步到生产环境，并触发弹窗跳转。
    """
    config_name = f"magistrate_config{magistrate_id}"
    try:
        config_data = utils.get_config(config_name)
        form_data = request.form

        cloud_config_path = config_data["client_magistrate"]["cloud"]
        cloud_config_path["sceptical_image"]["device_id"] = form_data.get("sceptical_device_id")
        cloud_config_path["sceptical_image"]["action_code"] = form_data.get("sceptical_action_code")
        cloud_config_path["patrol_image"]["device_id"] = form_data.get("patrol_device_id")
        cloud_config_path["patrol_image"]["action_code"] = form_data.get("patrol_action_code")

        utils.save_config(config_name, config_data)
        utils.sync_single_config(config_name)

        # 渲染回上一级面板，同时触发 HX-Trigger
        pipeline_config = utils.get_config("pipeline_config")
        inference_name = f"pipeline_inference_{magistrate_id}"
        alias = pipeline_config.get("client_pipeline", {}).get(inference_name, {}).get("alias", f"クライアント {magistrate_id}")
        ip_address = pipeline_config.get("client_pipeline", {}).get(inference_name, {}).get("camera_config", {}).get("address", "N/A")

        html = render_template('panel.html', magistrate_id=magistrate_id, alias=alias, ip_address=ip_address)
        resp = make_response(html)
        resp.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": "クラウド設定を保存しました"})
        return resp

    except (FileNotFoundError, KeyError, ValueError) as e:
        return f"Error updating cloud config for magistrate {magistrate_id}: {e}", 500


# --- 全局同步路由 (由 panel.html 的“确认”按钮使用) ---

@main_bp.route('/panel/sync/<int:magistrate_id>', methods=['POST'])
def sync_config(magistrate_id):
    """处理“確認”按钮的点击事件，同步对应的 magistrate 配置文件。"""
    config_name = f"magistrate_config{magistrate_id}"
    try:
        utils.sync_single_config(config_name)
        success_message = f"設定が同期されました ({config_name}.yaml)"
        response = make_response()
        response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": success_message})
        return response
    except Exception as e:
        return f'<span style="color: red;">同步失败: {e}</span>', 500


# NEW ROUTE: Sync all configurations
@main_bp.route('/config/sync_all', methods=['POST'])
def sync_all_configs():
    """
    同步所有 magistrate_configX.yaml 和 pipeline_config.yaml 文件。
    """
    try:
        for i in range(1, 9):
            config_name = f"magistrate_config{i}"
            utils.sync_single_config(config_name)

        utils.sync_single_config("pipeline_config")

        success_message = "すべての設定ファイルが同期されました！"
        response = make_response()
        response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": success_message})
        return response
    except Exception as e:
        return f'<span style="color: red;">一括同期失敗: {e}</span>', 500


# New route for "Initial Setup (Reset)"
@main_bp.route('/config/reset', methods=['POST'])
def reset_configs():
    """
    重置所有配置文件到默认状态，从 configs/defaults 复制到 configs 目录。
    """
    try:
        default_source_dir = os.path.join("configs", "defaults")
        local_configs_dir = "configs"
        utils.load_configs(default_source_dir, local_configs_dir)
        success_message = f"初期設定が読み込まれました"
        response = make_response()
        response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": success_message})
        return response
    except FileNotFoundError as e:
        return f'<span style="color: red;">初期設定のロードに失敗しました: {e}</span>', 500
    except Exception as e:
        return f'<span style="color: red;">初期設定のロード中にエラーが発生しました: {e}</span>', 500


# New route for "Load All" (from device)
@main_bp.route('/config/load_all', methods=['POST'])
def load_all_configs():
    """
    从设备的目标目录加载所有配置文件到本地的 'configs' 目录。
    """
    try:
        device_configs_dir = "/opt/SafeGuard/configs"
        local_configs_dir = "configs"
        utils.load_configs_from_device(device_configs_dir, local_configs_dir)
        success_message = f"デバイスから設定が読み込まれました"
        response = make_response()
        response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": success_message})
        return response
    except FileNotFoundError as e:
        return f'<span style="color: red;">デバイスからの読み込みに失敗しました: {e}</span>', 500
    except Exception as e:
        return f'<span style="color: red;">デバイスからの読み込み中にエラーが発生しました: {e}</span>', 500


# （示例）系统重启（模拟）
@main_bp.route('/system/restart', methods=['POST'])
def restart_system():
    """（ダミー）システムの再起動をシミュレートします。"""
    print("--- ACTION: Restarting system ---")
    # 这里可以加实际重启逻辑
    response = make_response()
    response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": "システムは正常に再起動されました！"})
    return response
