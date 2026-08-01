#!/usr/bin/env python3
"""补全仅有 posed_joints 的 Kimodo/SOMA NPZ（无 global_rot_mats）。

用于 smoothstep 插值等后处理只保存关节位置、未保存旋转矩阵的情况。
不需要 GPU 或重新跑 Kimodo；纯 NumPy，从骨骼方向推算 global/local 旋转。

用法:
  python complete_npz_from_posed_joints.py motion22.npz -o motion22_complete.npz
  python complete_npz_from_posed_joints.py motion22.npz --in-place
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKIN = Path(r"D:\Downloads\kimodo_stream\kimodo\assets\skeletons\somaskel77\skin_standard.npz")
FALLBACK_META = ROOT / "vendor" / "soma77_skeleton_meta.json"
SOMA_JOINTS = 77


def find_skin_npz() -> Path:
    for candidate in (
        DEFAULT_SKIN,
        ROOT.parent.parent / "kimodo_stream" / "kimodo" / "assets" / "skeletons" / "somaskel77" / "skin_standard.npz",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("找不到 somaskel77/skin_standard.npz，请用 --skin 指定路径")


def load_skeleton_meta(skin_path: Path) -> dict:
    skin = np.load(skin_path)
    names = [str(x) for x in skin["rig_joint_names"]]
    if len(names) != SOMA_JOINTS:
        raise ValueError(f"期望 {SOMA_JOINTS} 关节，skin 里为 {len(names)}")
    parents = np.full(SOMA_JOINTS, -1, dtype=np.int32)
    for parent_idx, child_idx in skin["rig_joint_connections"]:
        parents[int(child_idx)] = int(parent_idx)
    neutral = skin["bind_rig_transform"][:, :3, 3].astype(np.float64)
    neutral -= neutral[0]
    children: list[list[int]] = [[] for _ in range(SOMA_JOINTS)]
    for joint_idx, parent_idx in enumerate(parents):
        if parent_idx >= 0:
            children[parent_idx].append(joint_idx)
    return {
        "names": names,
        "parents": parents,
        "children": children,
        "neutral": neutral,
    }


def export_skeleton_meta_json(skin_path: Path, out_path: Path) -> None:
    meta = load_skeleton_meta(skin_path)
    payload = {
        "numJoints": SOMA_JOINTS,
        "names": meta["names"],
        "parents": meta["parents"].tolist(),
        "neutral": meta["neutral"].reshape(-1).tolist(),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    print(f"Wrote skeleton meta → {out_path}")


def rot_from_to(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    a = np.asarray(src, dtype=np.float64)
    b = np.asarray(dst, dtype=np.float64)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return np.eye(3, dtype=np.float64)
    a /= na
    b /= nb
    axis = np.cross(a, b)
    cos_angle = float(np.clip(np.dot(a, b), -1.0, 1.0))
    sin_angle = np.linalg.norm(axis)
    if sin_angle < 1e-8:
        if cos_angle > 0.0:
            return np.eye(3, dtype=np.float64)
        ortho = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        axis = np.cross(a, ortho)
        axis /= np.linalg.norm(axis)
        sin_angle = 1.0
        cos_angle = -1.0
    else:
        axis /= sin_angle
    k = np.array(
        [
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0],
        ],
        dtype=np.float64,
    )
    return np.eye(3, dtype=np.float64) + k + k @ k * ((1.0 - cos_angle) / (sin_angle * sin_angle))


def topological_order(parents: np.ndarray, root_idx: int = 0) -> list[int]:
    order: list[int] = []
    stack = [root_idx]
    while stack:
        joint_idx = stack.pop()
        order.append(joint_idx)
        stack.extend(
            child_idx
            for child_idx in range(len(parents))
            if parents[child_idx] == joint_idx
        )
    return order


def primary_child(joint_idx: int, neutral: np.ndarray, children: list[list[int]]) -> int | None:
    child_list = children[joint_idx]
    if not child_list:
        return None
    return max(child_list, key=lambda child: np.linalg.norm(neutral[child] - neutral[joint_idx]))


def estimate_root_global_rotation(
    posed_frame: np.ndarray,
    neutral: np.ndarray,
    children: list[list[int]],
    root_idx: int = 0,
) -> np.ndarray:
    spine_children = [child for child in children[root_idx] if "Spine" in str(child)]
    spine_child = spine_children[0] if spine_children else primary_child(root_idx, neutral, children)
    if spine_child is None:
        return np.eye(3, dtype=np.float64)
    rest_dir = neutral[spine_child] - neutral[root_idx]
    pose_dir = posed_frame[spine_child] - posed_frame[root_idx]
    return rot_from_to(rest_dir, pose_dir)


def estimate_global_rotations(
    posed_joints: np.ndarray,
    neutral: np.ndarray,
    parents: np.ndarray,
    children: list[list[int]],
    root_idx: int = 0,
) -> np.ndarray:
    num_frames, num_joints, _ = posed_joints.shape
    order = topological_order(parents, root_idx)
    global_rots = np.zeros((num_frames, num_joints, 3, 3), dtype=np.float32)

    for frame_idx in range(num_frames):
        posed_frame = posed_joints[frame_idx]
        global_frame = np.tile(np.eye(3, dtype=np.float64), (num_joints, 1, 1))
        for joint_idx in order:
            child_idx = primary_child(joint_idx, neutral, children)
            if child_idx is not None:
                rest_dir = neutral[child_idx] - neutral[joint_idx]
                pose_dir = posed_frame[child_idx] - posed_frame[joint_idx]
            elif int(parents[joint_idx]) >= 0:
                parent_idx = int(parents[joint_idx])
                rest_dir = neutral[joint_idx] - neutral[parent_idx]
                pose_dir = posed_frame[joint_idx] - posed_frame[parent_idx]
            else:
                continue
            if np.linalg.norm(rest_dir) < 1e-8 or np.linalg.norm(pose_dir) < 1e-8:
                continue
            global_frame[joint_idx] = rot_from_to(rest_dir, pose_dir)
        global_rots[frame_idx] = global_frame.astype(np.float32)
    return global_rots


def global_to_local_rotations(global_rots: np.ndarray, parents: np.ndarray, root_idx: int = 0) -> np.ndarray:
    num_frames, num_joints, _, _ = global_rots.shape
    local_rots = np.zeros_like(global_rots)
    for frame_idx in range(num_frames):
        for joint_idx in range(num_joints):
            parent_idx = int(parents[joint_idx])
            if parent_idx < 0:
                local_rots[frame_idx, joint_idx] = global_rots[frame_idx, joint_idx]
            else:
                parent_global = global_rots[frame_idx, parent_idx].astype(np.float64)
                joint_global = global_rots[frame_idx, joint_idx].astype(np.float64)
                local_rots[frame_idx, joint_idx] = (parent_global.T @ joint_global).astype(np.float32)
    return local_rots


def fk_positions(
    local_rots: np.ndarray,
    root_positions: np.ndarray,
    neutral: np.ndarray,
    parents: np.ndarray,
    root_idx: int = 0,
) -> np.ndarray:
    num_frames, num_joints, _, _ = local_rots.shape
    order = topological_order(parents, root_idx)
    posed = np.zeros((num_frames, num_joints, 3), dtype=np.float64)
    for frame_idx in range(num_frames):
        global_rots = np.tile(np.eye(3), (num_joints, 1, 1))
        for joint_idx in order:
            parent_idx = int(parents[joint_idx])
            if parent_idx < 0:
                global_rots[joint_idx] = local_rots[frame_idx, joint_idx]
            else:
                global_rots[joint_idx] = global_rots[parent_idx] @ local_rots[frame_idx, joint_idx]
        posed[frame_idx, root_idx] = root_positions[frame_idx]
        for joint_idx in order:
            if joint_idx == root_idx:
                continue
            parent_idx = int(parents[joint_idx])
            offset = neutral[joint_idx] - neutral[parent_idx]
            posed[frame_idx, joint_idx] = posed[frame_idx, parent_idx] + global_rots[parent_idx] @ offset
    return posed.astype(np.float32)


def complete_npz_dict(raw: dict, meta: dict) -> dict:
    if "global_rot_mats" in raw:
        return dict(raw)
    if "posed_joints" not in raw:
        raise ValueError("NPZ 缺少 posed_joints，无法补全")

    posed = np.asarray(raw["posed_joints"], dtype=np.float32)
    if posed.ndim != 3 or posed.shape[1] != SOMA_JOINTS:
        raise ValueError(f"posed_joints 应为 (T, {SOMA_JOINTS}, 3)，当前 {posed.shape}")

    if "root_positions" in raw:
        root_positions = np.asarray(raw["root_positions"], dtype=np.float32)
    else:
        root_positions = posed[:, 0, :].copy()

    neutral = meta["neutral"]
    parents = meta["parents"]
    children = meta["children"]

    global_rots = estimate_global_rotations(posed.astype(np.float64), neutral, parents, children)
    local_rots = global_to_local_rotations(global_rots, parents)
    print("已从 posed_joints 估算 global_rot_mats / local_rot_mats（后处理 NPZ 可用，精度低于 Kimodo 原始输出）")

    out = dict(raw)
    out["posed_joints"] = posed
    out["root_positions"] = root_positions.astype(np.float32)
    out["global_rot_mats"] = global_rots.astype(np.float32)
    out["local_rot_mats"] = local_rots.astype(np.float32)
    if "fps" not in out:
        out["fps"] = np.float32(30.0)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="从 posed_joints 补全 global_rot_mats")
    parser.add_argument("input", nargs="?", type=Path, help="输入 .npz（仅 posed_joints 或缺 global_rot_mats）")
    parser.add_argument("-o", "--output", type=Path, help="输出路径（默认: <name>_complete.npz）")
    parser.add_argument("--in-place", action="store_true", help="覆盖原文件")
    parser.add_argument("--skin", type=Path, help="somaskel77/skin_standard.npz 路径")
    parser.add_argument("--export-meta", type=Path, help="仅导出 vendor/soma77_skeleton_meta.json 后退出")
    args = parser.parse_args()

    skin_path = args.skin or find_skin_npz()
    if args.export_meta:
        export_skeleton_meta_json(skin_path, args.export_meta)
        return

    if not args.input:
        parser.error("需要 input，或使用 --export-meta")

    meta = load_skeleton_meta(skin_path)
    with np.load(args.input, allow_pickle=False) as z:
        raw = {k: z[k] for k in z.files if not k.startswith("note")}

    completed = complete_npz_dict(raw, meta)
    if args.in_place:
        out_path = args.input
    else:
        out_path = args.output or args.input.with_name(f"{args.input.stem}_complete.npz")

    save_kwargs = {k: v for k, v in completed.items() if isinstance(v, np.ndarray) or np.isscalar(v)}
    np.savez(out_path, **save_kwargs)
    print(f"已写入 {out_path}")
    print(f"  keys: {sorted(save_kwargs.keys())}")


if __name__ == "__main__":
    main()
