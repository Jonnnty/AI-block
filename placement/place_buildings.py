#!/usr/bin/env python3
"""Merge placed buildings (full PLY) onto base terrain using placements.json.

Design with lightweight models (outputs_50pct/), save placements.json,
then merge with full models (outputs/) by matching filename.

  python place_buildings.py --base map1.ply --config placements.json --out scene.ply
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
OUTPUTS = Path(r"D:\Downloads\outputs")
if not OUTPUTS.is_dir():
    OUTPUTS = ROOT / "outputs"


def read_ply(path: str) -> tuple[list[str], np.ndarray, int]:
    with open(path, "rb") as f:
        header_lines: list[str] = []
        while True:
            line = f.readline().decode("ascii")
            header_lines.append(line)
            if line.strip() == "end_header":
                break
        props: list[str] = []
        vertex_count = 0
        for line in header_lines:
            if line.startswith("element vertex"):
                vertex_count = int(line.split()[-1])
            if line.startswith("property float"):
                props.append(line.split()[-1])
        n_props = len(props)
        data = np.frombuffer(f.read(vertex_count * n_props * 4), dtype=np.float32)
        if data.size != vertex_count * n_props:
            raise ValueError(f"unexpected size in {path}")
        return header_lines, data.reshape(vertex_count, n_props), n_props


def write_ply(path: str, header_template: list[str], data: np.ndarray) -> None:
    n = data.shape[0]
    header: list[str] = []
    for line in header_template:
        if line.startswith("element vertex"):
            header.append(f"element vertex {n}\n")
        else:
            header.append(line)
    with open(path, "wb") as f:
        f.write("".join(header).encode("ascii"))
        data.astype(np.float32).tofile(f)


def yaw_matrix(yaw_rad: float) -> np.ndarray:
    c, s = math.cos(yaw_rad), math.sin(yaw_rad)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)


def transform_gaussian_block(block: np.ndarray, placement: dict) -> np.ndarray:
    out = block.copy()
    scale = float(placement.get("scale", 1.0))
    yaw = math.radians(float(placement.get("yaw_deg", 0.0)))
    tx = float(placement.get("x", 0.0))
    ty = float(placement.get("y", 0.0))
    tz = float(placement.get("z", 0.0))

    xyz = out[:, 0:3]
    center = placement.get("center")
    if center is not None:
        # center = [centroid_x, centroid_y, bottom_z] — bottom-aligned anchor
        xyz = xyz - np.asarray(center, dtype=np.float32)

    R = yaw_matrix(yaw)
    xyz = (xyz @ R.T) * scale
    xyz += np.array([tx, ty, tz], dtype=np.float32)
    out[:, 0:3] = xyz

    if out.shape[1] >= 13:
        out[:, 10:13] += math.log(max(scale, 1e-6))

    if out.shape[1] >= 17:
        half = yaw * 0.5
        out[:, 13:17] = 0.0
        out[:, 13] = math.cos(half)
        out[:, 16] = math.sin(half)

    return out


def resolve_asset_path(asset_name: str) -> Path:
    name = Path(asset_name).name
    for candidate in (OUTPUTS / name, ROOT / "outputs" / name, ROOT / name):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"full model not found: {name} (looked in {OUTPUTS})")


def load_placements(config_path: Path) -> list:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        placements = raw.get("placements")
        if isinstance(placements, list):
            return placements
    raise ValueError("config must be a JSON list or v2 object with placements")


def merge_scene(base_path: Path, config_path: Path, out_path: Path) -> None:
    base_header, base_data, n_props = read_ply(str(base_path))
    merged = [base_data]

    placements = load_placements(config_path)

    for i, p in enumerate(placements):
        asset = resolve_asset_path(p["asset"])
        _, block, n = read_ply(str(asset))
        if n != n_props:
            raise ValueError(f"{asset}: property count {n} != base {n_props}")
        merged.append(transform_gaussian_block(block, p))
        print(f"[{i+1}] {p['asset']} -> x={p.get('x',0)} y={p.get('y',0)} scale={p.get('scale',1)}")

    out = np.vstack(merged)
    write_ply(str(out_path), base_header, out)
    print(f"saved {out_path} ({out.shape[0]:,} gaussians)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="map1.ply")
    ap.add_argument("--config", default="placements.json")
    ap.add_argument("--out", default="scene.ply")
    args = ap.parse_args()
    merge_scene(ROOT / args.base, ROOT / args.config, ROOT / args.out)


if __name__ == "__main__":
    main()
