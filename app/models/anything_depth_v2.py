#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Depth-Anything v2 (ONNX) - OpenCV DNN 推理脚本
------------------------------------------------
功能：
- 加载 ONNX 模型（先 onnx.checker 校验，再交给 OpenCV DNN 推理）
- 优先尝试 CUDA（支持 FP16），失败自动回退 CPU
- 支持 Unicode 路径的图像读写（Windows/Linux 通用）
- 预处理：BGR->RGB、归一化、标准化、NCHW
- 后处理：按 2%~98% 百分位做对比度拉伸，可视化为伪彩色
- 输出：可视化 PNG + 原始 float32 深度 NPY

注意：
- 本脚本输出的是“相对深度/深度值”，并非真实米制距离。若要换算为实际距离，
  需要相机内参、畸变参数、绝对尺度等额外信息。
"""

from pathlib import Path
from typing import Tuple, Optional

import cv2
import numpy as np


# ---------------------------
# 预处理 / 后处理
# ---------------------------
def preprocess_bgr_for_onnx(
    bgr: np.ndarray,
    size_wh: Tuple[int, int] = (518, 518),
    mean: Tuple[float, float, float] = (0.5, 0.5, 0.5),
    std: Tuple[float, float, float] = (0.5, 0.5, 0.5),
) -> np.ndarray:
    """
    将 BGR 图像预处理为模型输入张量：
    - resize 到 (W,H)
    - BGR->RGB
    - 归一化到 [0,1]
    - 标准化 (img - mean) / std
    - NCHW + float32
    """
    w, h = size_wh
    img = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_LINEAR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    img = (img - mean) / std
    blob = np.transpose(img, (2, 0, 1))[np.newaxis, ...].astype(np.float32)
    return blob


def postprocess_depth_to_vis(
    depth: np.ndarray,
    out_size_wh: Tuple[int, int],
    pmin: float = 2.0,
    pmax: float = 98.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    将模型输出的 depth（可能形状为 [N,1,H,W] / [1,H,W] / [H,W]）：
    - 统一到 [H,W]
    - resize 到可视化目标尺寸 (W,H)
    - 按百分位拉伸对比度 (pmin~pmax)
    - 伪彩色可视化

    返回：
    - vis: uint8 的伪彩色图 (H,W,3)
    - depth_resized: float32 的深度矩阵 (H,W)
    """
    if isinstance(depth, (list, tuple)):
        depth = depth[0]
    # 统一到 2D
    if depth.ndim == 4:         # [N,1,H,W]
        depth = depth[0, 0]
    elif depth.ndim == 3:       # [1,H,W]
        depth = depth[0]
    elif depth.ndim == 2:
        pass
    else:
        raise ValueError(f"不支持的深度输出维度: {depth.shape}")

    W, H = out_size_wh
    depth_resized = cv2.resize(depth.astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)

    d = depth_resized
    d_min = np.percentile(d, pmin)
    d_max = np.percentile(d, pmax)
    denom = max(1e-6, (d_max - d_min))
    d_norm = np.clip((d - d_min) / denom, 0.0, 1.0)
    gray = (d_norm * 255.0).astype(np.uint8)

    # TURBO 不可用时回退到 JET
    try:
        vis = cv2.applyColorMap(gray, cv2.COLORMAP_TURBO)
    except Exception:
        vis = cv2.applyColorMap(gray, cv2.COLORMAP_JET)

    return vis, depth_resized


# ---------------------------
# DNN Backend 选择
# ---------------------------
def set_dnn_backend_safely(net: cv2.dnn_Net, prefer_cuda: bool = True) -> str:
    """
    优先尝试 CUDA（有 FP16 就用 FP16），否则回退 CPU。
    返回实际使用的模式: "cuda" / "cpu"
    """
    mode = "cpu"
    if prefer_cuda:
        try:
            info = cv2.getBuildInformation()
            has_dnn = "To be built:                YES" in info or "DNN:                        YES" in info
            has_cuda = ("NVIDIA CUDA" in info) and ("cuDNN" in info) and has_dnn
            if has_cuda:
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                # 优先 FP16
                if hasattr(cv2.dnn, "DNN_TARGET_CUDA_FP16"):
                    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA_FP16)
                else:
                    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                mode = "cuda"
                print("[DNN] 已选择 CUDA 后端。")
            else:
                print("[DNN] OpenCV 未启用 CUDA DNN，使用 CPU。")
        except Exception as e:
            print("[DNN] 选择 CUDA 后端失败，回退 CPU。Err:", e)

    if mode == "cpu":
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    return mode


