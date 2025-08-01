# utils.py

import os
import shutil

import yaml

def get_config(config_name: str):
    """
    从 'configs' 目录读取指定的 YAML 配置文件。

    Args:
        config_name (str): 配置文件的名称 (不带 .yaml 后缀)。

    Returns:
        dict: 解析后的配置数据。

    Raises:
        FileNotFoundError: 如果配置文件不存在。
    """
    # 构建配置文件的完整路径
    filepath = os.path.join("configs", f"{config_name}.yaml")
    print(f"Loading config from {filepath}")

    # 检查文件是否存在
    if not os.path.isfile(filepath):
        print(f"File {filepath} does not exist.")
        raise FileNotFoundError(f"Configuration file '{filepath}' not found")

    # 读取并解析 YAML 文件
    with open(filepath, 'r', encoding='utf-8') as file:
        config_data = yaml.safe_load(file)
    return config_data


def save_config(config_name: str, data: dict):
    """
    将数据保存为 YAML 文件到 'configs' 目录。

    Args:
        config_name (str): 配置文件的名称 (不带 .yaml 后缀)。
        data (dict): 需要保存的数据。
    """
    # 构建配置文件的完整路径
    filepath = os.path.join("configs", f"{config_name}.yaml")
    print(f"Saving config to {filepath}")

    # 将 Python 字典写入 YAML 文件
    with open(filepath, 'w', encoding='utf-8') as file:
        # default_flow_style=False 使其输出为更易读的块样式
        # sort_keys=False 保持字典中的键顺序
        yaml.dump(data, file, default_flow_style=False, sort_keys=False, allow_unicode=True)

# 保留旧函数以实现向后兼容，但新的路由将使用通用函数
def get_magistrate_config_in_json(file_id: int):
    filename = f"magistrate_config{file_id}"
    return get_config(filename)


# --- 以下是新增/移动的函数 ---

def load_configs(src_folder: str, dest_folder: str):
    """
    将源文件夹中的所有 .yaml 文件复制到目标文件夹。
    如果目标文件夹不存在，则会创建它。
    """
    # 检查源文件夹是否存在
    if not os.path.isdir(src_folder):
        raise FileNotFoundError(f"源文件夹不存在或不是一个目录: {src_folder}")

    # 确保目标文件夹存在
    os.makedirs(dest_folder, exist_ok=True)

    copied_files = []

    # 遍历源文件夹中的所有文件
    for filename in os.listdir(src_folder):
        if filename.endswith(".yaml"):
            src_path = os.path.join(src_folder, filename)
            dest_path = os.path.join(dest_folder, filename)

            # 复制文件并保留元数据
            shutil.copy2(src_path, dest_path)
            copied_files.append(filename)
            print(f"已复制 {src_path} 到 {dest_path}")

    return copied_files


def has_configs(proj_dir: str = "/opt/SafeGuard/configs") -> bool:
    """检查指定目录中是否存在核心配置文件。"""
    if not os.path.isdir(proj_dir):
        return False
    # 检查是否存在 magistrate, pipeline, 和 recorder 的配置文件
    magistrate_found = any(f.startswith("magistrate_config") and f.endswith(".yaml") for f in os.listdir(proj_dir))
    pipeline_found = os.path.exists(os.path.join(proj_dir, "pipeline_config.yaml"))
    recorder_found = os.path.exists(os.path.join(proj_dir, "recorder_config.yaml"))
    return magistrate_found and pipeline_found and recorder_found


def synchronize_configs(target_dir: str = "/opt/SurveillanceServiceRestfulAPIs/configs",
                        source_dir: str = "/opt/SafeGuard/configs"):
    """
    在应用启动时，从主配置目录同步配置到应用目录。
    如果主目录缺少配置，则会尝试从 './configs/defaults' 加载默认配置。
    """
    # 1. 首先检查主配置目录 (source_dir)
    if has_configs(source_dir):
        print(f"在主目录 '{source_dir}' 中找到有效配置。")
        print(f"正在从 '{source_dir}' 同步配置到 '{target_dir}'...")
        load_configs(source_dir, target_dir)
        return

    # 2. 如果主目录无效，则尝试从默认目录加载
    print(f"主目录 '{source_dir}' 中未找到必要的配置，尝试从默认位置加载。")
    
    # 定义默认配置的源目录
    default_source_dir = os.path.join("configs", "defaults")

    # 检查默认目录是否存在
    if os.path.isdir(default_source_dir):
        print(f"正在从默认目录 '{default_source_dir}' 同步配置到 '{target_dir}'...")
        load_configs(default_source_dir, target_dir)
    else:
        # 3. 如果默认目录也不存在，则报告错误
        print(f"严重错误：主目录 '{source_dir}' 和默认目录 '{default_source_dir}' 均无法提供配置。")
        print("应用可能无法正常启动。请检查配置！")
