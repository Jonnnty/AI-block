#!/usr/bin/env python3
"""Concatenate Kimodo motion.npz segments along the frame axis (in order)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def concat_npz_segments(paths: list[Path]) -> dict[str, np.ndarray]:
    if not paths:
        raise ValueError("no input NPZ files")
    chunks = [load_npz(p) for p in paths]
    keys = chunks[0].keys()
    for i, chunk in enumerate(chunks[1:], start=2):
        if chunk.keys() != keys:
            raise ValueError(f"key mismatch in segment {i}: {chunk.keys()} vs {keys}")

    out: dict[str, np.ndarray] = {}
    for key in keys:
        arrs = [c[key] for c in chunks]
        ref_shape = arrs[0].shape[1:]
        for i, arr in enumerate(arrs):
            if arr.shape[1:] != ref_shape:
                raise ValueError(
                    f"{key}: shape mismatch in segment {i + 1}: {arr.shape} vs {arrs[0].shape}"
                )
            if arr.dtype != arrs[0].dtype:
                raise ValueError(
                    f"{key}: dtype mismatch in segment {i + 1}: {arr.dtype} vs {arrs[0].dtype}"
                )
        out[key] = np.concatenate(arrs, axis=0)
    return out


def save_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="motion.npz files in order")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="output motion.npz path",
    )
    args = parser.parse_args(argv)
    inputs = [p.resolve() for p in args.inputs]
    for p in inputs:
        if not p.is_file():
            print(f"missing: {p}", file=sys.stderr)
            return 1
    merged = concat_npz_segments(inputs)
    save_npz(args.output.resolve(), merged)
    frames = merged["posed_joints"].shape[0]
    joints = merged["posed_joints"].shape[1]
    print(f"Wrote {args.output} ({frames} frames, {joints} joints, {len(inputs)} segments)")
    for p in inputs:
        n = load_npz(p)["posed_joints"].shape[0]
        print(f"  + {p.name} ({p.parent.name}): {n} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
