#!/usr/bin/env python3
"""Export SOMA skin_standard.npz to a compact binary for browser LBS."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKIN = (
    Path(__file__).resolve().parents[2].parent / "kimodo_stream" / "kimodo" / "assets" / "skeletons" / "somaskel77" / "skin_standard.npz"
)
FALLBACK_SKIN = Path(r"D:\Downloads\kimodo_stream\kimodo\assets\skeletons\somaskel77\skin_standard.npz")
OUT = ROOT / "vendor" / "soma_skin.bin"
MAGIC = b"SOMASKIN"


def find_skin_path() -> Path:
    for candidate in (DEFAULT_SKIN, FALLBACK_SKIN):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("skin_standard.npz not found; set path via argv[1]")


def main() -> None:
    skin_path = Path(sys.argv[1]) if len(sys.argv) > 1 else find_skin_path()
    data = np.load(skin_path)
    bind_vertices = np.asarray(data["bind_vertices"], dtype=np.float32)
    faces = np.asarray(data["faces"], dtype=np.uint32)
    lbs_indices = np.asarray(data["lbs_indices"], dtype=np.uint8)
    lbs_weights = np.asarray(data["lbs_weights"], dtype=np.float32)
    bind_rig = np.asarray(data["bind_rig_transform"], dtype=np.float32)
    bind_rig_inv = np.linalg.inv(bind_rig).astype(np.float32)

    num_verts = bind_vertices.shape[0]
    num_faces = faces.shape[0]
    num_joints = bind_rig.shape[0]
    max_inf = lbs_indices.shape[1]

    floor_y = float(bind_vertices[:, 1].min())

    header = struct.pack(
        "<8s5I1f",
        MAGIC,
        1,
        num_verts,
        num_faces,
        num_joints,
        max_inf,
        floor_y,
    )
    payload = b"".join(
        [
            bind_vertices.tobytes(order="C"),
            faces.tobytes(order="C"),
            lbs_indices.tobytes(order="C"),
            lbs_weights.tobytes(order="C"),
            bind_rig_inv.tobytes(order="C"),
        ]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(header + payload)
    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT} ({size_kb:.1f} KB, V={num_verts}, F={num_faces}, J={num_joints})")


if __name__ == "__main__":
    main()
