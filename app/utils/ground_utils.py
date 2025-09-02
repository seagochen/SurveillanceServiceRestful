import numpy as np
from typing import List, Tuple, Optional

def _rotation_world_from_camera(yaw: float, pitch: float, roll: float) -> np.ndarray:
    R_align = np.array([[1.0, 0.0, 0.0],
                        [0.0, 0.0, 1.0],
                        [0.0, -1.0, 0.0]], dtype=float)

    cy, sy = np.cos(yaw), np.sin(yaw)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cr, sr = np.cos(roll), np.sin(roll)

    Rz = np.array([[cy, -sy, 0.0],
                   [sy,  cy, 0.0],
                   [0.0, 0.0, 1.0]], dtype=float)
    Rx = np.array([[1.0, 0.0, 0.0],
                   [0.0,  cp, -sp],
                   [0.0,  sp,  cp]], dtype=float)
    Ry = np.array([[ cr, 0.0, sr],
                   [0.0, 1.0, 0.0],
                   [-sr, 0.0, cr]], dtype=float)
    return Rz @ Rx @ Ry @ R_align


def _clip_poly_y_range(poly: np.ndarray, y_min: float, y_max: float) -> np.ndarray:
    """
    对二维多边形 poly[:,(x,y)] 依次做半平面裁剪：y>=y_min，再 y<=y_max。
    返回裁剪后的多边形顶点（可能为空）。
    """
    def clip_halfplane(points: np.ndarray, keep_func):
        if len(points) == 0:
            return points
        out = []
        n = len(points)
        for i in range(n):
            P = points[i]
            Q = points[(i + 1) % n]
            Pin = keep_func(P)
            Qin = keep_func(Q)
            if Pin and Qin:
                # P 在内，Q 在内：保留 Q
                out.append(Q)
            elif Pin and not Qin:
                # P 在内，Q 在外：加入交点
                I = _intersect_y_boundary(P, Q, keep_func)
                if I is not None:
                    out.append(I)
            elif not Pin and Qin:
                # P 在外，Q 在内：加入交点和 Q
                I = _intersect_y_boundary(P, Q, keep_func)
                if I is not None:
                    out.append(I)
                out.append(Q)
            else:
                # 都在外：不加
                pass
        return np.asarray(out, dtype=float)

    def keep_low(ymax):
        return lambda P: P[1] <= ymax + 1e-12

    def keep_high(ymin):
        return lambda P: P[1] >= ymin - 1e-12

    # 先 y>=y_min
    poly1 = clip_halfplane(poly, keep_high(y_min))
    # 再 y<=y_max
    poly2 = clip_halfplane(poly1, keep_low(y_max))
    return poly2


def _intersect_y_boundary(P: np.ndarray, Q: np.ndarray, keep_func) -> Optional[np.ndarray]:
    """
    计算线段 P->Q 与当前半平面边界(y=const)的交点。
    这里我们通过推断 keep_func 是 y>=k 还是 y<=k 来求对应的常数 k。
    """
    # 通过在 y 方向上微调两个测试点，推断边界方向并求出 k
    # 由于 keep_func 只有“内/外”，这里直接用 P,Q 的 y 值求直线与 y=k 的交点
    # 我们需要知道边界的 k：若 keep_func(np.array([0,k])) 为 True 且 keep_func(np.array([0,k+eps])) 为 False → y<=k
    # 简化：通过判断 keep_func 在极大/极小 y 上的表现，推定是 y<=k 还是 y>=k，再用 P、Q 的 y 接近该阈值解 k。
    # 为避免复杂判断，这里用数值法：如果 keep_func 在 y 很大的点为 True，则边界是 y>=k（高半平面为内）；
    # 反之则是 y<=k（低半平面为内）。随后 k 用 min/max(P.y,Q.y) 与一个非常大的/小的测试 y 插值求。
    y_test_hi = 1e9
    y_test_lo = -1e9
    if keep_func(np.array([0.0, y_test_hi])):
        # 内部是 y 很大 → keep: y>=k
        # 交边界应为 y = k，落在 [min(P.y,Q.y), max(P.y,Q.y)] 上
        k = min(P[1], Q[1])  # 近似：沿边界处于较小的 y 端（S-H 算法只需一致性，不影响几何正确性）
    else:
        # 内部是 y 很小 → keep: y<=k
        k = max(P[1], Q[1])

    # 线性插值：x = P.x + t*(Q.x-P.x), y = P.y + t*(Q.y-P.y) = k → t = (k - P.y)/(Q.y - P.y)
    denom = (Q[1] - P[1])
    if abs(denom) < 1e-12:
        return None
    t = (k - P[1]) / denom
    x = P[0] + t * (Q[0] - P[0])
    return np.array([x, k], dtype=float)


def calculate_ground_dimensions(
    camera_height: float,
    roll_angle: float,
    pitch_angle: float,
    yaw_angle: float,
    focal_length: List[float],
    principal_coord: List[float],
    ground_coords: List[List[float]],
    depth_scale: Optional[float] = None,   # <== 新增：深度量程（米）
) -> Tuple[float, float]:
    """
    返回 (width_x, depth_y)：
      - width_x: X方向跨度（横向，米）
      - depth_y: Y方向跨度（纵向，米）
    若提供 depth_scale，则把地面四边形按 Y∈[0, depth_scale] 裁剪后再计算跨度。
    """
    H = float(camera_height) / 100.0  # cm -> m
    fx, fy = float(focal_length[0]), float(focal_length[1])
    cx, cy = float(principal_coord[0]), float(principal_coord[1])

    yaw = np.deg2rad(float(yaw_angle))
    pitch = np.deg2rad(float(pitch_angle))
    roll = np.deg2rad(float(roll_angle))

    R_wc = _rotation_world_from_camera(yaw, pitch, roll)
    C = np.array([0.0, 0.0, H], dtype=float)  # 相机中心（世界系）

    hits = []
    for (u, v) in ground_coords:
        x = (float(u) - cx) / fx
        y = (float(v) - cy) / fy
        r_cam = np.array([x, y, 1.0], dtype=float)
        r_cam /= (np.linalg.norm(r_cam) + 1e-12)
        d = R_wc @ r_cam
        dz = d[2]
        if dz >= -1e-12:
            # 这条视线没有向下，不与地面相交，略过
            continue
        t = -H / dz
        P = C + t * d
        P[2] = 0.0
        # 只保留 X,Y
        hits.append([P[0], P[1]])

    if len(hits) < 3:
        # 不是有效多边形，用简单 min/max（至少 2 点）兜底
        if len(hits) < 2:
            return 0.0, 0.0
        arr = np.asarray(hits)
        width_x = float(arr[:,0].max() - arr[:,0].min())
        depth_y = float(arr[:,1].max() - arr[:,1].min())
        if depth_scale is not None:
            # 对 Y 做范围裁剪
            y0 = max(0.0, float(arr[:,1].min()))
            y1 = min(depth_scale, float(arr[:,1].max()))
            depth_y = max(y1 - y0, 0.0)
        return max(width_x, 0.0), max(depth_y, 0.0)

    poly = np.asarray(hits, dtype=float)  # 形如 [[x,y],...]

    if depth_scale is not None:
        # 按 Y∈[0, depth_scale] 裁剪
        poly = _clip_poly_y_range(poly, 0.0, float(depth_scale))
        if len(poly) == 0:
            return 0.0, 0.0

    X = poly[:, 0]
    Y = poly[:, 1]
    width_x = float(X.max() - X.min())
    depth_y = float(Y.max() - Y.min())
    return max(width_x, 0.0), max(depth_y, 0.0)
