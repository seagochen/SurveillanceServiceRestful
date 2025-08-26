import paho.mqtt.client as mqtt
import os
import shutil

import yaml


def get_config(config_name: str,
               default_folder: str = "configs",
               return_path: bool = True):
    """
    从 'configs' 目录读取指定的 YAML 配置文件。
    """
    # 构建配置文件的完整路径
    filepath = os.path.join(default_folder, f"{config_name}.yaml")
    print(f"Loading config from {filepath}")

    # 检查文件是否存在
    if not os.path.isfile(filepath):
        print(f"File {filepath} does not exist.")
        raise FileNotFoundError(f"Configuration file '{filepath}' not found")
    # end-if

    if return_path:
        return filepath
    else:
        with open(filepath, "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            return config
        # end-with
    # end-if-else

def save_config(config_name: str, data: dict, default_folder: str = "configs"):
    """
    将数据保存为 YAML 文件到 'configs' 目录。

    Args:
        config_name (str): 配置文件的名称 (不带 .yaml 后缀)。
        data (dict): 需要保存的数据。
    """
    # 构建配置文件的完整路径
    filepath = os.path.join(default_folder, f"{config_name}.yaml")
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


def has_configs(proj_dir: str = "/opt/SurveillanceService/configs") -> bool:
    """检查指定目录中是否存在核心配置文件。"""
    if not os.path.isdir(proj_dir):
        return False
    # 检查是否存在 magistrate, pipeline, 和 recorder 的配置文件
    pipeline_file = os.path.join(proj_dir, "pipeline_config.yaml")
    magistrate_files = [f for f in os.listdir(proj_dir) if f.startswith("magistrate_config") and f.endswith(".yaml")]
    magistrate_files = [os.path.join(proj_dir, f) for f in magistrate_files]

    # Make sure the size of magistrate_files is at least 8
    if len(magistrate_files) < 8:
        return False

    # If pipeline_file exists, return True
    if os.path.isfile(pipeline_file):
        return True
    

def synchronize_configs(target_dir: str = "/opt/SurveillanceServiceRestful/configs",
                        source_dir: str = "/opt/SurveillanceService/configs"):
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


def sync_single_config(config_name: str, dest_folder: str = "/opt/SurveillanceService/configs"):
    """
    将单个指定的 .yaml 文件从本地 'configs' 目录同步到目标文件夹。

    Args:
        config_name (str): 配置文件的名称 (不带 .yaml 后缀)。
        dest_folder (str): 目标文件夹路径。

    Returns:
        str: 被同步的文件的完整目标路径。

    Raises:
        FileNotFoundError: 如果源文件不存在。
    """
    source_path = os.path.join("configs", f"{config_name}.yaml")

    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"源配置文件 '{source_path}' 不存在。")

    os.makedirs(dest_folder, exist_ok=True)

    dest_path = os.path.join(dest_folder, f"{config_name}.yaml")

    shutil.copy2(source_path, dest_path)
    print(f"已将 {source_path} 同步到 {dest_path}")
    return dest_path


def load_configs_from_device(source_dir: str = "/opt/SurveillanceService/configs", 
                             dest_dir: str = "configs"):
    """
    将目标设备上的配置 (source_dir) 复制回本地的 'configs' 目录 (dest_dir)。
    这相当于从设备“加载”配置。
    """
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"设备配置源文件夹不存在或不是一个目录: {source_dir}")

    os.makedirs(dest_dir, exist_ok=True)

    copied_files = []
    for filename in os.listdir(source_dir):
        if filename.endswith(".yaml"):
            src_path = os.path.join(source_dir, filename)
            dest_path = os.path.join(dest_dir, filename)
            shutil.copy2(src_path, dest_path)
            copied_files.append(filename)
            print(f"已从设备加载 {src_path} 到本地 {dest_path}")
    return copied_files


# 清空 MQTT 保留消息的函数
def clear_retained_status_messages(broker_host: str, broker_port: int, status_topics: list):
    """
    连接到 MQTT broker 并清除指定主题下的所有保留状态消息。

    Args:
        broker_host (str): MQTT broker 的主机地址。
        broker_port (int): MQTT broker 的端口。
        status_topics (list): 需要清除保留消息的主题列表，支持通配符。
    """
    try:
        # 使用一个独立的客户端来执行此任务
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "retained_message_cleaner")
        client.connect(broker_host, broker_port, 60)

        # 循环遍历所有需要清除的主题
        for topic in status_topics:
            # 发布一个空消息，并设置 retain=True，这将清除该主题下的保留消息
            client.publish(topic, payload=None, qos=0, retain=True)
            print(f"已清除主题 '{topic}' 的保留消息。")

        client.disconnect()
    except Exception as e:
        print(f"清空保留消息时发生错误: {e}")


def normalize(v):
    if v is None:
        return ""
    if isinstance(v, str) and v.strip().lower() == "none":
        return ""
    return v
