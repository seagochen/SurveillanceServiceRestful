import os
import shutil
from pathlib import Path
import traceback
from typing import Dict, List, Optional, Union

from flask import has_request_context, request

from pyengine.utils.logger import logger


def search_files(dir_path: Union[str, Path], pattern: str) -> List[Path]:
    """
    在指定目录下递归搜索匹配 pattern 的文件。

    Args:
        dir_path (Union[str, Path]): 要搜索的目录，可以是 str 或 Path。
        pattern (str): 通配符模式，例如 "*.yaml" 或 "pipeline_config.yaml"。

    Returns:
        List[Path]: 匹配到的文件路径列表。
    """
    dir_path = Path(dir_path)  # 支持 str/Path 两种输入

    if not dir_path.exists() or not dir_path.is_dir():
        raise FileNotFoundError(f"目录不存在: {dir_path}")

    return list(dir_path.rglob(pattern))


def get_config(config_name: str, default_folder: str = "configs"):
    # # --- 【新增】打印调用来源和堆栈信息 ---
    # print("-----------------------------------------------------")
    # # 检查是否在 Flask 请求上下文中，如果是，则打印请求信息
    # if has_request_context():
    #     print(f"DEBUG: get_config called from request: {request.method} {request.path}")
    # else:
    #     print("DEBUG: get_config called from outside of a request context")
    #
    # # 打印调用栈，limit=5 表示只显示最近的5层调用，避免日志过长
    # print("DEBUG: Call stack:")
    # traceback.print_stack(limit=5)
    # print("-----------------------------------------------------")
    # # --- 结束新增部分 ---

    candidates = [
        default_folder,
        os.environ.get("RESTFUL_CONFIG_DIR"),                 # 可通过环境变量注入
        "/opt/SurveillanceServiceRestful/configs",            # 运行时目标
        "/opt/SurveillanceServiceRestful/default",            # 默认兜底
        "/opt/SurveillanceService/configs",                   # 上游项目
    ]
    for folder in [p for p in candidates if p]:

        # 组合文件路径
        filepath = os.path.join(folder, f"{config_name}.yaml")

        # print(f"Loading config from {filepath}")

        # 发现目标文件
        if os.path.isfile(filepath):
            return filepath

    raise FileNotFoundError(f"Configuration file '{config_name}.yaml' not found in: {candidates}")


def copy_configs(
    src_folder: Union[str, Path],
    dest_folder: Union[str, Path],
    default_folder: Optional[str] = None,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
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

    def _has_target_configs(dir_path: Union[str, Path]) -> bool:
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            return False

        pipeline = dir_path / "pipeline_config.yaml"
        magistrate_configs = search_files(dir_path, "magistrate_config*.yaml")
        camera_configs = search_files(dir_path, "camera_parameters*.yaml")

        # 期望两者数量一致，且至少 8 份
        if not pipeline.exists():
            return False
        if len(magistrate_configs) < 8:
            return False
        if len(magistrate_configs) != len(camera_configs):
            return False
        return True

    dest = Path(dest_folder)
    src = Path(src_folder)
    default = Path(default_folder) if default_folder else None

    result = {"source": "none", "copied": [], "skipped": [], "failed": []}

    # 0) 目标目录已具备核心配置则直接返回
    if _has_target_configs(dest):
        logger.info("_has_core_configs",
                    f"The target directory already has the core configuration, skip copying: {dest}")
        result["source"] = "dest"
        return result

    # 1) 决定最终的来源目录：优先 src，其次 default
    chosen_source: Optional[Path] = None
    if _has_target_configs(src):
        chosen_source = src
        result["source"] = "src"
    elif default and _has_target_configs(default):
        chosen_source = default
        result["source"] = "default"
    else:
        # 找不到合适的，直接raise
        raise Exception("Error, yaml configuration files were not found, and no copy was performed.")

    # 2) 准备目标目录
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    # 3) 枚举来源目录中的 .yaml 并拷贝
    for src_file in search_files(chosen_source, "*.yaml"):
        dest_file = dest / src_file.name
        if dest_file.exists() and not overwrite:
            result["skipped"].append(src_file.name)
            logger.info("copy_configs", f"skipped {src_file.name}")
            continue
        try:
            if not dry_run:
                shutil.copy2(str(src_file), str(dest_file))
            result["copied"].append(src_file.name)
            logger.info("copy_configs", f"Copying {src_file.name} -> {dest_file}")
        except Exception as e:
            result["failed"].append(src_file.name)
            logger.error_trace("copy_configs", f"Failed, while copying {src_file.name} -> {dest_file}")

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

