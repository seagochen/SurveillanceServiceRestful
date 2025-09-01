import os
import shutil
from typing import Dict, List, Optional, Union
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


# def copy_configs(src_folder: str, dest_folder: str):
#     """
#     将源文件夹中的所有 .yaml 文件复制到目标文件夹。
#     如果目标文件夹不存在，则会创建它。
#     """
#     def _has_configs(proj_dir: str = "/opt/SurveillanceService/configs") -> bool | None:
#         """检查指定目录中是否存在核心配置文件。"""
#         if not os.path.isdir(proj_dir):
#             return False

#         # 检查是否存在 magistrate, pipeline 的配置文件
#         pipeline_file = os.path.join(proj_dir, "pipeline_config.yaml")
#         magistrate_files = [f for f in os.listdir(proj_dir) if
#                             f.startswith("magistrate_config") and f.endswith(".yaml")]
#         magistrate_files = [os.path.join(proj_dir, f) for f in magistrate_files]

#         # Make sure the size of magistrate_files is at least 8
#         if len(magistrate_files) < 8:
#             return False

#         # If pipeline_file exists, return True
#         if os.path.isfile(pipeline_file):
#             return True

#     # 检查源文件夹是否存在
#     if not os.path.isdir(src_folder):
#         raise FileNotFoundError(f"源文件夹不存在或不是一个目录: {src_folder}")

#     # 检查源文件是否有Yaml文件
#     if not _has_configs(src_folder):
#         logger.info("copy_configs", "Source folder has nothing to copy")
#         return []

#     # 确保目标文件夹存在
#     os.makedirs(dest_folder, exist_ok=True)

#     copied_files = []

#     # 遍历源文件夹中的所有文件
#     for filename in os.listdir(src_folder):
#         if filename.endswith(".yaml"):
#             src_path = os.path.join(src_folder, filename)
#             dest_path = os.path.join(dest_folder, filename)

#             # 复制文件并保留元数据
#             shutil.copy2(src_path, dest_path)
#             copied_files.append(filename)
#             logger.info("copy_configs", f"Copied {filename} to {dest_path}")

#     return copied_files

# from __future__ import annotations
# import os
# import shutil
# from pathlib import Path
# from typing import Iterable, List, Dict, Optional

def copy_configs(
    src_folder: str,
    dest_folder: str,
    default_folder: Optional[str] = None,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
    logger=None,
) -> Dict[str, List[str]]:
    """
    按优先级将 .yaml 配置拷贝到目标目录：
    1) 如果目标目录(dest_folder) 已具备核心配置 -> 不做任何拷贝。
    2) 否则尝试从 src_folder 拷贝核心配置与其它 .yaml。
    3) 若 src_folder 也不具备核心配置，且提供了 default_folder，则从 default_folder 回落拷贝。
    
    参数:
        src_folder:     首选配置来源目录（例如 /opt/SurveillanceService/configs）
        dest_folder:    目标目录（例如 /opt/SurveillanceServiceRestful/configs）
        default_folder: 回落配置目录（例如 项目内的 configs/default）
        overwrite:      同名文件是否覆盖（默认 False）
        dry_run:        只打印/返回将要发生的动作，不实际拷贝
        logger:         可选日志器，需具备 .info/.warning/.error
    
    返回:
        {
          "source": "dest|src|default|none",
          "copied": [...],     # 实际拷贝的文件名
          "skipped": [...],    # 因已存在且不覆盖而跳过
          "failed":  [...],    # 拷贝失败
        }
    """

    def _log(level: str, msg: str):
        if logger:
            getattr(logger, level)("copy_configs", msg)
        else:
            # 没有 logger 时退化打印
            print(f"[{level.upper()}] copy_configs: {msg}")

    def _has_core_configs(dir_path: Path) -> bool:
        if not dir_path.is_dir():
            return False
        pipeline = dir_path / "pipeline_config.yaml"
        magistrates = [p for p in dir_path.glob("magistrate_config*.yaml") if p.suffix == ".yaml"]
        if len(magistrates) < 8:
            return False
        return pipeline.is_file()

    def _collect_yaml(dir_path: Path) -> List[Path]:
        if not dir_path.is_dir():
            return []
        return [p for p in dir_path.iterdir() if p.is_file() and p.suffix == ".yaml"]

    dest = Path(dest_folder)
    src = Path(src_folder)
    default = Path(default_folder) if default_folder else None

    result = {"source": "none", "copied": [], "skipped": [], "failed": []}

    # 0) 目标目录已具备核心配置则直接返回
    if _has_core_configs(dest):
        _log("info", f"目标目录已具备核心配置，跳过拷贝: {dest}")
        result["source"] = "dest"
        return result

    # 1) 决定最终的来源目录：优先 src，其次 default
    chosen_source: Optional[Path] = None
    if _has_core_configs(src):
        chosen_source = src
        result["source"] = "src"
    elif default and _has_core_configs(default):
        chosen_source = default
        result["source"] = "default"
    else:
        # 两个来源都不满足核心条件，仍可选择“尽力而为”拷贝所有 .yaml（可选）
        # 这里保守处理：直接返回，不做非核心拷贝，避免混乱。
        _log("warning", "未在 src 或 default 找到完整的核心配置，未执行拷贝。")
        return result

    # 2) 准备目标目录
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    # 3) 枚举来源目录中的 .yaml 并拷贝
    for src_file in _collect_yaml(chosen_source):
        dest_file = dest / src_file.name
        if dest_file.exists() and not overwrite:
            result["skipped"].append(src_file.name)
            _log("info", f"已存在且不覆盖，跳过: {dest_file}")
            continue
        try:
            if not dry_run:
                shutil.copy2(str(src_file), str(dest_file))
            result["copied"].append(src_file.name)
            _log("info", f"复制 {src_file.name} -> {dest_file}")
        except Exception as e:
            result["failed"].append(src_file.name)
            _log("error", f"复制失败 {src_file} -> {dest_file}: {e}")

    return result



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

