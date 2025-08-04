import json
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
    """渲染并返回单个 magistrate 的配置面板页面。"""
    return render_template('panel.html', magistrate_id=magistrate_id)


# --- 摄像头配置面板路由 ---

@main_bp.route('/panel/camera/<int:magistrate_id>', methods=['GET'])
def get_camera_config_panel(magistrate_id):
    """显示指定 magistrate_id 的摄像头配置面板。"""
    try:
        pipeline_config = utils.get_config("pipeline_config")
        inference_name = f"pipeline_inference_{magistrate_id}"
        
        # 【关键修复】移除了 ["inferences"]，直接访问 "client_pipeline" 下的 inference_name
        inference_details = pipeline_config["client_pipeline"][inference_name]
        camera_config = inference_details["camera_config"]
        
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
    # try:
    #     config_data = utils.get_config(config_name)
    #     inference_name = f"pipeline_inference_{magistrate_id}"
    #     form_data = request.form.to_dict()

    #     # 【关键修复】移除了 ["inferences"]
    #     cam_config_path = config_data["client_pipeline"][inference_name]["camera_config"]
    #     cam_config_path["camera_id"] = form_data.get("camera_id")
    #     cam_config_path["address"] = form_data.get("address")
    #     cam_config_path["port"] = int(form_data.get("port"))
    #     cam_config_path["path"] = form_data.get("path")
    #     cam_config_path["username"] = form_data.get("username")
    #     cam_config_path["password"] = form_data.get("password")

    #     utils.save_config(config_name, config_data)
    #     utils.sync_single_config(config_name)

    #     success_message = "カメラ設定が保存・同期されました"
    #     response = make_response()
    #     response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": success_message})
    #     return response

    # except (FileNotFoundError, KeyError, ValueError) as e:
    #     return f"Error updating camera config for magistrate {magistrate_id}: {e}", 500
    try:
        config_data = utils.get_config(config_name)
        inference_name = f"pipeline_inference_{magistrate_id}"
        form_data = request.form.to_dict()

        cam_config_path = config_data["client_pipeline"][inference_name]["camera_config"]
        cam_config_path["camera_id"] = form_data.get("camera_id")
        cam_config_path["address"] = form_data.get("address")
        cam_config_path["port"] = int(form_data.get("port"))
        cam_config_path["path"] = form_data.get("path")
        cam_config_path["username"] = form_data.get("username")
        cam_config_path["password"] = form_data.get("password")

        utils.save_config(config_name, config_data)
        utils.sync_single_config(config_name)

        # 【关键修改】不再返回 HX-Trigger，而是直接渲染并返回 panel.html
        return render_template('panel.html', magistrate_id=magistrate_id)

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
    # try:
    #     config_data = utils.get_config(config_name)
    #     form_data = request.form
        
    #     # 更新内存中的配置
    #     cloud_config_path = config_data["client_magistrate"]["cloud"]
    #     cloud_config_path["sceptical_image"]["device_id"] = form_data.get("sceptical_device_id")
    #     cloud_config_path["sceptical_image"]["action_code"] = form_data.get("sceptical_action_code")
    #     cloud_config_path["patrol_image"]["device_id"] = form_data.get("patrol_device_id")
    #     cloud_config_path["patrol_image"]["action_code"] = form_data.get("patrol_action_code")

    #     # 1. 保存到本地
    #     utils.save_config(config_name, config_data)
        
    #     # 2. 【新增】立即同步到生产环境
    #     utils.sync_single_config(config_name)

    #     # 3. 【新增】返回带有 HX-Trigger 的响应，触发弹窗和跳转
    #     # success_message = f"クラウド設定が保存・同期されました" # "云设置已保存并同步"
    #     # response = make_response()
    #     # response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": success_message})
    #     # return response

    #     success_message = "クラウド設定が保存・同期されました"
    #     response = make_response()
    #     response.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": success_message})
    #     return response

    # except (FileNotFoundError, KeyError, ValueError) as e:
    #     return f"Error updating cloud config for magistrate {magistrate_id}: {e}", 500
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
        return render_template('panel.html', magistrate_id=magistrate_id)

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