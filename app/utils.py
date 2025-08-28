import os
import shutil
from typing import Optional, Union
from urllib.parse import quote

from pyengine.utils.logger import logger


def get_config(config_name: str,
               default_folder: str = "configs"):
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

    return filepath


def copy_configs(src_folder: str, dest_folder: str):
    """
    将源文件夹中的所有 .yaml 文件复制到目标文件夹。
    如果目标文件夹不存在，则会创建它。
    """
    def _has_configs(proj_dir: str = "/opt/SurveillanceService/configs") -> bool | None:
        """检查指定目录中是否存在核心配置文件。"""
        if not os.path.isdir(proj_dir):
            return False

        # 检查是否存在 magistrate, pipeline, 和 recorder 的配置文件
        pipeline_file = os.path.join(proj_dir, "pipeline_config.yaml")
        magistrate_files = [f for f in os.listdir(proj_dir) if
                            f.startswith("magistrate_config") and f.endswith(".yaml")]
        magistrate_files = [os.path.join(proj_dir, f) for f in magistrate_files]

        # Make sure the size of magistrate_files is at least 8
        if len(magistrate_files) < 8:
            return False

        # If pipeline_file exists, return True
        if os.path.isfile(pipeline_file):
            return True

    # 检查源文件夹是否存在
    if not os.path.isdir(src_folder):
        raise FileNotFoundError(f"源文件夹不存在或不是一个目录: {src_folder}")

    # 检查源文件是否有Yaml文件
    if not _has_configs(src_folder):
        logger.info("copy_configs", "Source folder has nothing to copy")
        return []

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
            logger.info("copy_configs", f"Copied {filename} to {dest_path}")

    return copied_files


def copy_single_config(config_name: str, dest_folder: str = "/opt/SurveillanceService/configs"):
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


def normalize(v):
    if v is None:
        return ""
    if isinstance(v, str) and v.strip().lower() == "none":
        return ""
    return v

