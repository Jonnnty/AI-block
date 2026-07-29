#!/usr/bin/env python3
"""Bake a compact LBS Gaussian shell from SOMA skin for browser motion splats."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKIN_NPZ = (
    Path(__file__).resolve().parents[2].parent
    / "kimodo_stream"
    / "kimodo"
    / "assets"
    / "skeletons"
    / "somaskel77"
    / "skin_standard.npz"
)
FALLBACK_SKIN_NPZ = Path(r"D:\Downloads\kimodo_stream\kimodo\assets\skeletons\somaskel77\skin_standard.npz")
DEFAULT_SKIN_BIN = ROOT / "vendor" / "soma_skin.bin"
OUT = ROOT / "vendor" / "motion_splat_shell.bin"
MAGIC = b"MOTSPLAT"
TARGET_SPLATS = 2000
DEFAULT_SPLAT_SCALE = 0.018
SHELL_COLOR = (0x98, 0xBD, 0xFF)
SHELL_OPACITY = 255


def y_up_pos_to_z_up(x: float, y: float, z: float) -> tuple[float, float, float]:
    return x, z, y


def find_skin_npz() -> Path | None:
    for candidate in (DEFAULT_SKIN_NPZ, FALLBACK_SKIN_NPZ):
        if candidate.is_file():
            return candidate
    return None


def load_from_skin_bin(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    raw = path.read_bytes()
    if raw[:8] != b"SOMASKIN":
        raise ValueError(f"{path} is not soma_skin.bin")
    num_verts = struct.unpack_from("<I", raw, 12)[0]
    num_faces = struct.unpack_from("<I", raw, 16)[0]
    max_inf = struct.unpack_from("<I", raw, 24)[0]
    off = 32
    bind_vertices = np.frombuffer(raw, dtype=np.float32, count=num_verts * 3, offset=off).reshape(num_verts, 3).copy()
    off += num_verts * 3 * 4
    off += num_faces * 3 * 4
    lbs_indices = np.frombuffer(raw, dtype=np.uint8, count=num_verts * max_inf, offset=off).reshape(num_verts, max_inf).copy()
    off += num_verts * max_inf
    lbs_weights = np.frombuffer(raw, dtype=np.float32, count=num_verts * max_inf, offset=off).reshape(num_verts, max_inf).copy()
    return bind_vertices, lbs_indices, lbs_weights, max_inf


def load_from_skin_npz(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    data = np.load(path)
    bind_vertices = np.asarray(data["bind_vertices"], dtype=np.float32)
    lbs_indices = np.asarray(data["lbs_indices"], dtype=np.uint8)
    lbs_weights = np.asarray(data["lbs_weights"], dtype=np.float32)
    max_inf = int(lbs_indices.shape[1])
    return bind_vertices, lbs_indices, lbs_weights, max_inf


def sample_shell(
    bind_vertices: np.ndarray,
    lbs_indices: np.ndarray,
    lbs_weights: np.ndarray,
    target: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    num_verts = bind_vertices.shape[0]
    step = max(1, num_verts // target)
    indices = np.arange(0, num_verts, step, dtype=np.uint32)
    if indices.shape[0] > target:
        indices = indices[:target]
    verts = bind_vertices[indices].copy()
    z_up = np.empty_like(verts)
    for i, (x, y, z) in enumerate(verts):
        z_up[i] = y_up_pos_to_z_up(float(x), float(y), float(z))
    return indices, z_up, lbs_indices[indices].copy(), lbs_weights[indices].copy()


def bake_shell(
    bind_vertices: np.ndarray,
    lbs_indices: np.ndarray,
    lbs_weights: np.ndarray,
    max_inf: int,
    target: int = TARGET_SPLATS,
    splat_scale: float = DEFAULT_SPLAT_SCALE,
) -> bytes:
    vert_indices, bind_z_up, shell_indices, shell_weights = sample_shell(
        bind_vertices, lbs_indices, lbs_weights, target
    )
    num_splats = bind_z_up.shape[0]
    header = struct.pack(
        "<8sIIIfBBBB",
        MAGIC,
        1,
        num_splats,
        max_inf,
        splat_scale,
        *SHELL_COLOR,
        SHELL_OPACITY,
    )
    payload = b"".join(
        [
            bind_z_up.astype(np.float32).tobytes(order="C"),
            shell_indices.astype(np.uint8).tobytes(order="C"),
            shell_weights.astype(np.float32).tobytes(order="C"),
            vert_indices.astype(np.uint32).tobytes(order="C"),
        ]
    )
    return header + payload


def main() -> None:
    skin_bin = Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].endswith(".bin") else DEFAULT_SKIN_BIN
    skin_npz = find_skin_npz()
    out_path = OUT
    if len(sys.argv) > 1 and sys.argv[-1].endswith(".bin") and Path(sys.argv[-1]) != skin_bin:
        out_path = Path(sys.argv[-1])

    if skin_bin.is_file():
        bind_vertices, lbs_indices, lbs_weights, max_inf = load_from_skin_bin(skin_bin)
        source = skin_bin
    elif skin_npz is not None:
        bind_vertices, lbs_indices, lbs_weights, max_inf = load_from_skin_npz(skin_npz)
        source = skin_npz
    elif len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        arg = Path(sys.argv[1])
        if arg.suffix == ".npz":
            bind_vertices, lbs_indices, lbs_weights, max_inf = load_from_skin_npz(arg)
            source = arg
        else:
            raise SystemExit(f"Unknown skin input: {arg}")
    else:
        raise SystemExit("SOMA skin not found. Run export_soma_skin.py first or pass skin_standard.npz.")

    blob = bake_shell(bind_vertices, lbs_indices, lbs_weights, max_inf)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)
    num_splats = struct.unpack_from("<I", blob, 12)[0]
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB, {num_splats} splats, source={source})")


if __name__ == "__main__":
    main()
