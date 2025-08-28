import os
import shutil
import sys
from typing import Optional, Union
from urllib.parse import quote

import yaml

from pyengine.utils.logger import logger


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


def generate_rtsp_url(address: str,
                      port: Optional[Union[int, str]] = None,
                      path: Optional[str] = None,
                      username: Optional[str] = None,
                      password: Optional[str] = None) -> str:
    """
    构造 RTSP URL（面向 OpenCV 等客户端）。

    - 忽略 "none"/空串/空白：统一视为 None
    - 自动剥离传入的 rtsp:// 或 rtsps:// 前缀
    - IPv6 地址在带端口时自动加方括号
    - 用户名/密码做 URL 编码；路径保留斜杠

    返回: 形如 rtsp://user:pass@host:port/path 的字符串
    generate_rtsp_url("rtsp://192.168.1.10", 554, "stream1", "user", "p@ss:123")
    # rtsp://user:p%40ss%3A123@192.168.1.10:554/stream1

    generate_rtsp_url("fe80::1", "8554", "/live.sdp")
    # rtsp://[fe80::1]:8554/live.sdp

    generate_rtsp_url("192.168.1.10", None, None, "admin", None)
    # rtsp://admin@192.168.1.10
    """

    def _norm(v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        return None if v == "" or v.lower() == "none" else v

    # --- 归一化输入 ---
    if not isinstance(address, str) or not address.strip():
        raise ValueError("address 不能为空")
    address = address.strip()

    # 去掉协议前缀
    lower = address.lower()
    if lower.startswith("rtsp://"):
        address = address[7:]
    elif lower.startswith("rtsps://"):
        address = address[8:]  # 这里只构造 rtsp://，如需 rtsps 可扩展

    path = _norm(path)
    username = _norm(username)
    password = _norm(password)

    # 端口处理：允许传 str，能转 int 则使用
    port_val: Optional[int] = None
    if port is not None:
        try:
            port_val = int(str(port).strip())
            if port_val <= 0 or port_val > 65535:
                port_val = None
        except (ValueError, TypeError):
            port_val = None

    # IPv6 包装（仅当显式带端口/需要加冒号时）
    # 判断：包含':' 且不含 '['（粗略判断是 IPv6 字面量）
    host = address
    needs_brackets = (":" in host) and not host.startswith("[")
    if needs_brackets and port_val is not None:
        host = f"[{host}]"

    # 用户认证（编码敏感字符）
    if username and password:
        auth = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    elif username and not password:
        auth = f"{quote(username, safe='')}@"
    else:
        auth = ""

    # 端口段
    port_part = f":{port_val}" if port_val is not None else ""

    # 路径段（保留斜杠；编码空格等，避免破坏 URL）
    if path:
        # 去重前导斜杠，只保留一个
        path_clean = "/" + path.lstrip("/")
        path_part = quote(path_clean, safe="/:@$-_.+!*'(),")
    else:
        path_part = ""

    return f"rtsp://{auth}{host}{port_part}{path_part}"
