#!/usr/bin/env python3
"""Concatenate Kimodo motion.npz segments with root translation stitching.

Each segment after the first stores motion in a local root frame whose frame-0
pose matches the previous segment's last pose. This script translates later
segments so the skeleton continues from the prior end position instead of
jumping back to the origin.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

POSITION_KEYS = frozenset({
    "root_positions",
    "smooth_root_pos",
    "posed_joints",
})


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def validate_chunks(chunks: list[dict[str, np.ndarray]]) -> None:
    if not chunks:
        raise ValueError("no input NPZ files")
    keys = chunks[0].keys()
    for i, chunk in enumerate(chunks[1:], start=2):
        if chunk.keys() != keys:
            raise ValueError(f"key mismatch in segment {i}: {chunk.keys()} vs {keys}")
    for key in keys:
        ref_shape = chunks[0][key].shape[1:]
        ref_dtype = chunks[0][key].dtype
        for i, chunk in enumerate(chunks):
            arr = chunk[key]
            if arr.shape[1:] != ref_shape:
                raise ValueError(
                    f"{key}: shape mismatch in segment {i + 1}: {arr.shape} vs {chunks[0][key].shape}"
                )
            if arr.dtype != ref_dtype:
                raise ValueError(
                    f"{key}: dtype mismatch in segment {i + 1}: {arr.dtype} vs {ref_dtype}"
                )


def apply_root_offset(chunk: dict[str, np.ndarray], offset: np.ndarray) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for key, arr in chunk.items():
        data = arr.copy()
        if key in POSITION_KEYS:
            data = data + offset.astype(data.dtype, copy=False)
        out[key] = data
    return out


def boundary_pose_error(prev_last: np.ndarray, next_first: np.ndarray, offset: np.ndarray) -> float:
    aligned = next_first.astype(np.float64) + offset.astype(np.float64)
    return float(np.max(np.abs(aligned - prev_last.astype(np.float64))))


def concat_npz_segments(
    paths: list[Path],
    *,
    skip_duplicate_boundary_frames: bool = True,
) -> dict[str, np.ndarray]:
    chunks = [load_npz(p) for p in paths]
    validate_chunks(chunks)

    stitched: list[dict[str, np.ndarray]] = []
    prev_last_root: np.ndarray | None = None

    for i, chunk in enumerate(chunks):
        piece = {k: v.copy() for k, v in chunk.items()}
        if i > 0:
            assert prev_last_root is not None
            first_root = piece["root_positions"][0].astype(np.float64)
            offset = prev_last_root - first_root
            err = boundary_pose_error(
                stitched[-1]["posed_joints"][-1],
                piece["posed_joints"][0],
                offset,
            )
            if err > 1e-3:
                print(
                    f"warning: segment {i + 1} first pose differs from previous last "
                    f"after root offset (max err {err:.6f})",
                    file=sys.stderr,
                )
            piece = apply_root_offset(piece, offset)
            if skip_duplicate_boundary_frames:
                piece = {k: v[1:] for k, v in piece.items()}

        stitched.append(piece)
        prev_last_root = piece["root_positions"][-1].astype(np.float64)

    out: dict[str, np.ndarray] = {}
    for key in chunks[0].keys():
        out[key] = np.concatenate([part[key] for part in stitched], axis=0)
    return out


def save_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="motion.npz files in order")
    parser.add_argument("-o", "--output", type=Path, required=True, help="output motion.npz path")
    parser.add_argument(
        "--keep-duplicate-frames",
        action="store_true",
        help="keep the duplicated boundary frame on each segment after the first",
    )
    args = parser.parse_args(argv)
    inputs = [p.resolve() for p in args.inputs]
    for p in inputs:
        if not p.is_file():
            print(f"missing: {p}", file=sys.stderr)
            return 1

    merged = concat_npz_segments(
        inputs,
        skip_duplicate_boundary_frames=not args.keep_duplicate_frames,
    )
    save_npz(args.output.resolve(), merged)
    frames = merged["posed_joints"].shape[0]
    joints = merged["posed_joints"].shape[1]
    print(f"Wrote {args.output} ({frames} frames, {joints} joints, {len(inputs)} segments, stitched)")
    for p in inputs:
        n = load_npz(p)["posed_joints"].shape[0]
        print(f"  + {p.name} ({p.parent.name}): {n} frames")
    rp = merged["root_positions"]
    print(f"  root path: start {rp[0]} -> end {rp[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
