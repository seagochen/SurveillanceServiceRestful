import json
from time import time
from flask import Blueprint, jsonify, make_response, render_template, request

from app import utils

# 创建一个蓝图实例
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


# --- Magistrate 面板路由 ---

@main_bp.route('/panel/magistrate/<int:magistrate_id>')
def magistrate_panel(magistrate_id):
    """渲染并返回单个 magistrate 的配置面板页面，包含 alias 和 IP。"""
    try:
        pipeline_config = utils.get_config("pipeline_config")
        inference_name = f"pipeline_inference_{magistrate_id}"
        
        # Get alias and IP address for the panel header
        alias = pipeline_config.get("client_pipeline", {}).get(inference_name, {}).get("alias", f"クライアント {magistrate_id}")
        ip_address = pipeline_config.get("client_pipeline", {}).get(inference_name, {}).get("camera_config", {}).get("address", "N/A")
        
        return render_template('panel.html', magistrate_id=magistrate_id, alias=alias, ip_address=ip_address)
    except FileNotFoundError:
        return f"Error: pipeline_config.yaml not found!", 500
    except KeyError:
        return f"Error: Configuration for {inference_name} not found in pipeline_config.yaml!", 500
    except Exception as e:
        return f"Error loading panel for magistrate {magistrate_id}: {e}", 500



@main_bp.route('/panel/magistrate/<int:magistrate_id>/toggle_button', methods=['GET'])
def get_toggle_button(magistrate_id):
    """
    根据 pipeline_config.yaml 的内容，返回对应的“启用/禁用”按钮。
    """
    try:
        config = utils.get_config("pipeline_config")
        source_name = f"pipeline_inference_{magistrate_id}"
        
        # 检查 source_name 是否在 enable_sources 列表中
        enabled_sources = config.get("client_pipeline", {}).get("enable_sources", [])
        is_enabled = source_name in enabled_sources
        
        return render_template(
            '_toggle_button.html', 
            magistrate_id=magistrate_id, 
            is_enabled=is_enabled
        )
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


# --- 摄像头配置面板路由 ---

@main_bp.route('/panel/camera/<int:magistrate_id>', methods=['GET'])
def get_camera_config_panel(magistrate_id):
    """显示指定 magistrate_id 的摄像头配置面板。"""
    try:
        pipeline_config = utils.get_config("pipeline_config")
        inference_name = f"pipeline_inference_{magistrate_id}"

        inference_details = pipeline_config["client_pipeline"][inference_name]
        camera_config = inference_details["camera_config"]

        # Pass the alias to the camera_config dictionary so it can be accessed in the template
        camera_config['alias'] = inference_details.get('alias', f"クライアント {magistrate_id}")

        return render_template('camera_config_panel.html', magistrate_id=magistrate_id, config=camera_config)
    except (FileNotFoundError, KeyError) as e:
        error_message = (
            f"<h1>配置错误</h1>"
            f"<p>无法为 <strong>magistrate {magistrate_id}</strong> 加载配置。</p>"
            f"<p>请检查您的 <code>pipeline_config.yaml</code> 文件，确保路径 "
            f"<code>client_pipeline.{inference_name}.camera_config</code> 存在。</p>"
            f"<hr><p><strong>具体错误:</strong> {e}</p>"
        )
        return error_message, 500
    except Exception as e:
        return f"渲染模板时发生意外错误: {str(e)}", 500


@main_bp.route('/panel/camera/<int:magistrate_id>', methods=['POST'])
def update_camera_config_panel(magistrate_id):
    """更新摄像头配置，保存、同步并触发弹窗跳转。"""
    config_name = "pipeline_config"
    try:
        config_data = utils.get_config(config_name)
        inference_name = f"pipeline_inference_{magistrate_id}"
        form_data = request.form.to_dict()

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

        # 【关键修改】重新获取更新后的 alias 和 ip_address，并传递给 panel.html
        updated_pipeline_config = utils.get_config("pipeline_config") # 重新加载配置
        updated_inference_details = updated_pipeline_config["client_pipeline"][inference_name]
        updated_alias = updated_inference_details.get('alias', f"クライアント {magistrate_id}")
        updated_ip_address = updated_inference_details.get('camera_config', {}).get("address", "N/A")

        return render_template('panel.html', magistrate_id=magistrate_id, alias=updated_alias, ip_address=updated_ip_address)

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

        # 【关键修改】不再返回 HX-Trigger，而是直接渲染并返回 panel.html
        # 在这里也需要重新获取 alias 和 ip_address，以防万一
        pipeline_config = utils.get_config("pipeline_config")
        inference_name = f"pipeline_inference_{magistrate_id}"
        alias = pipeline_config.get("client_pipeline", {}).get(inference_name, {}).get("alias", f"クライアント {magistrate_id}")
        ip_address = pipeline_config.get("client_pipeline", {}).get(inference_name, {}).get("camera_config", {}).get("address", "N/A")

        return render_template('panel.html', magistrate_id=magistrate_id, alias=alias, ip_address=ip_address)

    except (FileNotFoundError, KeyError, ValueError) as e:
        return f"Error updating cloud config for magistrate {magistrate_id}: {e}", 500


# --- 全局同步路由 (现在由 panel.html 中的按钮使用) ---

@main_bp.route('/panel/sync/<int:magistrate_id>', methods=['POST'])
def sync_config(magistrate_id):
    """处理“確認”按钮的点击事件，同步对应的 magistrate 配置文件。"""
    config_name = f"magistrate_config{magistrate_id}"
    try:
        utils.sync_single_config(config_name)
        success_message = f"設定が同期されました ({config_name}.yaml)" # "设置已同步"
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
        # Assuming there are 8 magistrates as per the index.html grid
        for i in range(1, 9):
            config_name = f"magistrate_config{i}"
            utils.sync_single_config(config_name)
        
        # Also sync pipeline_config.yaml
        utils.sync_single_config("pipeline_config")

        success_message = "すべての設定ファイルが同期されました！" # "All configuration files have been synchronized!"
        response = make_response()
        response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": success_message})
        return response
    except Exception as e:
        return f'<span style="color: red;">一括同期失敗: {e}</span>', 500


# --- 其他路由 ---

@main_bp.route('/system/restart', methods=['POST'])
def restart_system():
    """（ダミー）システムの再起動をシミュレートします。"""
    # TODO: 実際の再起動ロジックを実装する必要があります
    print("--- ACTION: Restarting system ---")
    # ここに実際の再起動ロジックを実装します
    time.sleep(2) # 処理をシミュレート
    response = make_response()
    response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": "システムは正常に再起動されました！"})
    return response