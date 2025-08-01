import os
import random
import time
from flask import Blueprint, current_app, jsonify, render_template, request

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
    显示指定 magistrate_id 的摄像头配置面板，并添加了调试步骤。
    """
    try:
        # 读取主配置文件
        pipeline_config = utils.get_config("pipeline_config")
        inference_name = f"pipeline_inference_{magistrate_id}"
        
        # 提取出对应的摄像头配置
        inference_details = pipeline_config["client_pipeline"][inference_name]
        camera_config = inference_details["camera_config"]
        
        # 渲染模板
        return render_template('camera_config_panel.html', magistrate_id=magistrate_id, config=camera_config)
    
    except (FileNotFoundError, KeyError) as e:
        return f"Error loading config for magistrate {magistrate_id}: {e}", 404
    except Exception as e:
        # 捕捉其他渲染错误
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
    

# --- Monitor 路由 (保持不变) ---

@main_bp.route('/monitor/<string:monitor_id>', methods=['GET'])
def get_monitor_info(monitor_id):
    # 这里可以添加逻辑来获取指定的监控信息
    return jsonify({"message": f"Monitor {monitor_id} endpoint"})