from flask import Blueprint, json, jsonify, make_response, render_template, request

from app import utils

# 创建一个蓝图实例
# 第一个参数是蓝图的名称，第二个参数是模块的名称
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


# --- Magistrate 面板路由 ---

@main_bp.route('/panel/magistrate/<int:magistrate_id>')
def magistrate_panel(magistrate_id):
    """
    渲染并返回单个 magistrate 的配置面板页面。
    """
    # 这里将来可以从数据库或文件中加载 magistrate_id 对应的具体配置
    # 现在我们只把 magistrate_id 传递给模板
    return render_template('panel.html', magistrate_id=magistrate_id)

# --- 摄像头配置面板路由 ---

@main_bp.route('/panel/camera/<int:magistrate_id>', methods=['GET'])
def get_camera_config_panel(magistrate_id):
    """
    显示指定 magistrate_id 的摄像头配置面板。
    """
    try:
        # 1. 读取整个 pipeline_config.yaml 文件
        pipeline_config = utils.get_config("pipeline_config")
        inference_name = f"pipeline_inference_{magistrate_id}"
        
        # 2. 【关键】严格按照 YAML 的层级进行访问
        #    根据您的 pydantic 解析器，所有 pipeline_inference_* 都被放入了 "inferences" 字典中
        inference_details = pipeline_config["client_pipeline"]["inferences"][inference_name]
        
        # 3. 从中提取出 camera_config
        camera_config = inference_details["camera_config"]
        
        # 4. 将提取出的 camera_config 数据传递给模板
        return render_template('camera_config_panel.html', magistrate_id=magistrate_id, config=camera_config)
    
    except (FileNotFoundError, KeyError) as e:
        # 如果中间任何一个键 (Key) 不存在，就会触发 KeyError
        error_message = (
            f"<h1>配置错误</h1>"
            f"<p>无法为 <strong>magistrate {magistrate_id}</strong> 加载配置。</p>"
            f"<p>请检查您的 <code>pipeline_config.yaml</code> 文件，确保路径 "
            f"<code>client_pipeline.inferences.pipeline_inference_{magistrate_id}</code> "
            f"及其下的 <code>camera_config</code> 存在。</p>"
            f"<hr>"
            f"<p><strong>具体错误:</strong> {e}</p>"
        )
        return error_message, 500
    except Exception as e:
        return f"渲染模板时发生意外错误: {str(e)}", 500


@main_bp.route('/panel/camera/<int:magistrate_id>', methods=['POST'])
def update_camera_config_panel(magistrate_id):
    """
    更新并保存指定 magistrate_id 的摄像头配置。
    """
    try:
        # 1. 读取现有的完整配置
        config_data = utils.get_config("pipeline_config")
        inference_name = f"pipeline_inference_{magistrate_id}"
        
        # 2. 从 POST 请求的表单中获取新数据
        new_camera_config = request.form.to_dict()

        # 3. 更新内存中的配置字典
        #    注意：表单中的 'port' 是字符串，需要转为整数
        config_data["client_pipeline"]["inferences"][inference_name]["camera_config"]["camera_id"] = new_camera_config.get("camera_id")
        config_data["client_pipeline"]["inferences"][inference_name]["camera_config"]["address"] = new_camera_config.get("address")
        config_data["client_pipeline"]["inferences"][inference_name]["camera_config"]["port"] = int(new_camera_config.get("port"))
        config_data["client_pipeline"]["inferences"][inference_name]["camera_config"]["path"] = new_camera_config.get("path")
        config_data["client_pipeline"]["inferences"][inference_name]["camera_config"]["username"] = new_camera_config.get("username")
        config_data["client_pipeline"]["inferences"][inference_name]["camera_config"]["password"] = new_camera_config.get("password")

        # 4. 调用 utils 函数将修改后的完整配置写回文件
        utils.save_config("pipeline_config", config_data)
        
        # 5. 【重要】保存成功后，重新渲染并返回上一级的面板，给用户一个清晰的反馈
        return render_template('panel.html', magistrate_id=magistrate_id)

    except (FileNotFoundError, KeyError, ValueError) as e:
        return f"Error updating config for magistrate {magistrate_id}: {e}", 500


# --- API 路由 ---

# --- Magistrate 配置路由 ---
@main_bp.route('/config/magistrate/<int:magistrate_id>', methods=['GET'])
def get_magistrate_config(magistrate_id):
    """根据 ID 获取 magistrate 的配置。"""
    config_name = f"magistrate_config{magistrate_id}"
    try:
        # 调用通用函数读取配置
        config_data = utils.get_config(config_name)
        return jsonify(config_data)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@main_bp.route('/config/magistrate/<int:magistrate_id>', methods=['POST'])
def update_magistrate_config(magistrate_id):
    """根据 ID 更新 magistrate 的配置。"""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided in the request body"}), 400

    config_name = f"magistrate_config{magistrate_id}"
    try:
        # 调用通用函数保存配置
        utils.save_config(config_name, data)
        return jsonify({"message": f"Magistrate config '{config_name}.yaml' updated successfully.", "data": data}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to save configuration: {str(e)}"}), 500


@main_bp.route('/panel/cloud/<int:magistrate_id>', methods=['GET'])
def get_cloud_config_panel(magistrate_id):
    """
    显示指定 magistrate_id 的云配置面板。
    """
    try:
        config_name = f"magistrate_config{magistrate_id}"
        magistrate_config = utils.get_config(config_name)
        
        # 提取出 "cloud" 部分的配置
        cloud_config = magistrate_config["client_magistrate"]["cloud"]
        
        return render_template('cloud_config_panel.html', magistrate_id=magistrate_id, config=cloud_config)
    
    except (FileNotFoundError, KeyError) as e:
        return f"Error loading cloud config for magistrate {magistrate_id}: {e}", 404


@main_bp.route('/panel/cloud/<int:magistrate_id>', methods=['POST'])
def update_cloud_config_panel(magistrate_id):
    """
    更新并保存指定 magistrate_id 的云配置。
    """
    try:
        config_name = f"magistrate_config{magistrate_id}"
        config_data = utils.get_config(config_name)
        
        # 从表单中获取新数据
        form_data = request.form
        
        # 更新内存中的配置字典
        config_data["client_magistrate"]["cloud"]["sceptical_image"]["device_id"] = form_data.get("sceptical_device_id")
        config_data["client_magistrate"]["cloud"]["sceptical_image"]["action_code"] = form_data.get("sceptical_action_code")
        config_data["client_magistrate"]["cloud"]["patrol_image"]["device_id"] = form_data.get("patrol_device_id")
        config_data["client_magistrate"]["cloud"]["patrol_image"]["action_code"] = form_data.get("patrol_action_code")

        # 将修改后的完整配置写回文件
        utils.save_config(config_name, config_data)
        
        # 保存成功后，重新渲染并返回上一级的面板
        return render_template('panel.html', magistrate_id=magistrate_id)

    except (FileNotFoundError, KeyError, ValueError) as e:
        return f"Error updating cloud config for magistrate {magistrate_id}: {e}", 500


# --- Pipeline 配置路由 ---

@main_bp.route('/config/pipeline', methods=['GET'])
def get_pipeline_config():
    """获取 pipeline 的配置。"""
    try:
        config_data = utils.get_config("pipeline_config")
        return jsonify(config_data)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@main_bp.route('/config/pipeline', methods=['POST'])
def update_pipeline_config():
    """更新 pipeline 的配置。"""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided in the request body"}), 400

    try:
        utils.save_config("pipeline_config", data)
        return jsonify({"message": "Pipeline config 'pipeline_config.yaml' updated successfully.", "data": data}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to save configuration: {str(e)}"}), 500


# --- Recorder 配置路由 ---

@main_bp.route('/config/recorder', methods=['GET'])
def get_recorder_config():
    """获取 recorder 的配置。"""
    try:
        config_data = utils.get_config("recorder_config")
        return jsonify(config_data)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@main_bp.route('/config/recorder', methods=['POST'])
def update_recorder_config():
    """更新 recorder 的配置。"""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided in the request body"}), 400

    try:
        utils.save_config("recorder_config", data)
        return jsonify({"message": "Recorder config 'recorder_config.yaml' updated successfully.", "data": data}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to save configuration: {str(e)}"}), 500


# --- 新增的全局配置同步路由 ---

@main_bp.route('/config/update_all', methods=['GET'])
def update_all_configs():
    """
    将本服务 'configs' 文件夹内的所有 .yaml 文件同步到 '/opt/SafeGuard/configs'。
    这个操作会用本服务的配置覆盖目标文件夹中的同名文件。
    """
    source_folder = "configs"  # API服务自己的配置目录
    destination_folder = "/opt/SafeGuard/configs"  # 目标主配置目录

    try:
        # 调用 utils 中的函数来执行文件复制
        copied_files = utils.load_configs(source_folder, destination_folder)

        if not copied_files:
            message = f"源目录 '{source_folder}' 为空或不包含 .yaml 文件，没有文件被复制。"
        else:
            message = f"成功将 {len(copied_files)} 个配置文件同步到 '{destination_folder}'。"

        return jsonify({
            "message": message,
            "synced_files": copied_files
        }), 200

    except FileNotFoundError as e:
        # 如果源文件夹 'configs' 不存在
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        # 捕捉其他潜在错误 (如权限问题)
        return jsonify({"error": f"同步过程中发生意外错误: {str(e)}"}), 500


# @main_bp.route('/panel/sync/<int:magistrate_id>', methods=['POST'])
# def sync_config(magistrate_id):
#     """
#     处理“確認”按钮的点击事件，同步对应的 magistrate 配置文件。
#     成功后，触发前端事件以显示弹窗。
#     """
#     config_name = f"magistrate_config{magistrate_id}"
#     try:
#         synced_path = utils.sync_single_config(config_name)
        
#         # 【关键修改】我们将把成功消息作为事件的参数发送
#         success_message = f"同期成功！({config_name}.yaml)"
        
#         response = make_response() # 返回一个空的响应体即可
        
#         # 【关键修改】触发一个带有 JSON 数据的事件
#         # Alpine.js 将能接收到 'showSuccessModal' 事件和 success_message 的内容
#         response.headers['HX-Trigger'] = json.dumps({
#             "showSuccessModal": success_message
#         })
        
#         return response
    
#     except Exception as e:
#         # 失败时依然返回错误信息片段
#         return f'<span style="color: red;">同步失败: {e}</span>', 500

# @main_bp.route('/panel/sync/<int:magistrate_id>', methods=['POST'])
# def sync_config(magistrate_id):
#     """
#     Handles the "Confirm" button click, syncs the corresponding magistrate config file.
#     On success, it triggers a redirect back to the home page.
#     """
#     config_name = f"magistrate_config{magistrate_id}"
#     try:
#         utils.sync_single_config(config_name)
        
#         # Create a response to add a header
#         response = make_response()
        
#         # 【The Fix】Use HX-Redirect to command the browser to navigate to '/'
#         response.headers['HX-Redirect'] = '/'
        
#         return response
    
#     except Exception as e:
#         return f'<span style="color: red;">Sync failed: {e}</span>', 500

@main_bp.route('/panel/sync/<int:magistrate_id>', methods=['POST'])
def sync_config(magistrate_id):
    """
    处理“確認”按钮的点击事件，同步对应的 magistrate 配置文件。
    成功后，触发前端事件以显示弹窗。
    """
    config_name = f"magistrate_config{magistrate_id}"
    try:
        synced_path = utils.sync_single_config(config_name)
        success_message = f"設定が保存されました ({config_name}.yaml)"
        
        response = make_response()
        
        # 【关键修改】确保事件名是全小写的 "showsuccessmodal"
        response.headers['HX-Trigger'] = json.dumps({
            "showsuccessmodal": success_message
        })
        
        return response
    
    except Exception as e:
        return f'<span style="color: red;">同步失败: {e}</span>', 500

# --- Monitor 路由 (保持不变) ---

@main_bp.route('/monitor/<string:monitor_id>', methods=['GET'])
def get_monitor_info(monitor_id):
    # 这里可以添加逻辑来获取指定的监控信息
    return jsonify({"message": f"Monitor {monitor_id} endpoint"})