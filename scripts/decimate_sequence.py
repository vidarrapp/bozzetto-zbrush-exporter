#!/usr/bin/env python3
"""Batch-decimate an OBJ sequence for the Bozzetto timelapse viewer.

The ``bozzetto-zbrush-exporter`` ZScript produces one OBJ per undo-history
step (``sculpt_0001.obj`` ... ``sculpt_NNNN.obj``) at whatever subdivision
level the artist chose. Those meshes are usually far denser than Bozzetto
wants. Bozzetto recommends *a few thousand to a few hundred thousand
triangles per frame*; this script decimates the whole sequence down to a
target in one command, preserving filenames (and therefore frame order).

It uses PyMeshLab's quadric edge-collapse decimation -- the same algorithm
MeshLab exposes interactively -- so results match the artist's manual
workflow.

Usage
-----
    # Decimate every sculpt_*.obj to ~50k faces, write to ./decimated/
    python decimate_sequence.py ./raw ./decimated --faces 50000

    # Or by ratio (keep 5% of faces)
    python decimate_sequence.py ./raw ./decimated --percentage 0.05

Install the one dependency first:
    pip install pymeshlab

Note on units: "faces" here means triangles. Bozzetto reads triangle count,
so target faces == target triangles for the triangulated OBJs ZBrush emits.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _load_pymeshlab():
    """Import pymeshlab with a friendly message if it is missing."""
    try:
        import pymeshlab  # noqa: PLC0415  (deferred import for clean --help)
    except ImportError:
        sys.exit(
            "error: pymeshlab is not installed.\n"
            "       Install it with:  pip install pymeshlab\n"
            "       (PyMeshLab bundles MeshLab's filters; no separate "
            "MeshLab install is required.)"
        )
    return pymeshlab


def _decimation_filter(ms, target_faces: int | None, percentage: float | None,
                       preserve_boundary: bool, preserve_normals: bool):
    """Apply quadric edge-collapse decimation across PyMeshLab versions.

    The filter was renamed between PyMeshLab releases:
      * <= 2021.x : 'simplification_quadric_edge_collapse_decimation'
      * >= 2022.2 : 'meshing_decimation_quadric_edge_collapse'
    We try the new name first and fall back to the old one so the script
    works on whatever the artist has installed.
    """
    params = dict(
        preservenormal=preserve_normals,
        preserveboundary=preserve_boundary,
        preservetopology=False,
        autoclean=True,
        planarquadric=True,
    )
    if target_faces is not None:
        params["targetfacenum"] = int(target_faces)
    if percentage is not None:
        params["targetperc"] = float(percentage)

    for filter_name in (
        "meshing_decimation_quadric_edge_collapse",
        "simplification_quadric_edge_collapse_decimation",
    ):
        try:
            ms.apply_filter(filter_name, **params)
            return
        except Exception:  # pyright: ignore -- name not present in this version
            continue
    raise RuntimeError(
        "Could not find a quadric edge-collapse filter in this PyMeshLab "
        "version. Run `pymeshlab.print_filter_list()` to see available names."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Batch-decimate an OBJ sequence for Bozzetto.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_dir", type=Path, help="Folder of source OBJ files.")
    parser.add_argument("output_dir", type=Path, help="Folder for decimated OBJ files.")
    parser.add_argument(
        "--pattern", default="sculpt_*.obj",
        help="Glob for the meshes to process (matches the exporter's prefix).",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--faces", type=int,
        help="Target triangle count per frame (e.g. 50000).",
    )
    target.add_argument(
        "--percentage", type=float,
        help="Target fraction of original faces to keep, 0-1 (e.g. 0.05).",
    )
    parser.add_argument(
        "--keep-boundary", action="store_true",
        help="Preserve open mesh borders during decimation.",
    )
    parser.add_argument(
        "--no-preserve-normals", action="store_true",
        help="Do not try to preserve the normal directions (slightly faster).",
    )
    args = parser.parse_args(argv)

    if args.percentage is not None and not (0.0 < args.percentage <= 1.0):
        parser.error("--percentage must be in the range (0, 1].")

    pymeshlab = _load_pymeshlab()

    files = sorted(args.input_dir.glob(args.pattern))
    if not files:
        sys.exit(
            f"error: no files matching '{args.pattern}' in {args.input_dir}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Decimating {len(files)} mesh(es) from {args.input_dir} "
          f"-> {args.output_dir}")
    for i, src in enumerate(files, start=1):
        dst = args.output_dir / src.name
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(src))
        before = ms.current_mesh().face_number()
        _decimation_filter(
            ms,
            target_faces=args.faces,
            percentage=args.percentage,
            preserve_boundary=args.keep_boundary,
            preserve_normals=not args.no_preserve_normals,
        )
        after = ms.current_mesh().face_number()
        ms.save_current_mesh(str(dst))
        print(f"  [{i}/{len(files)}] {src.name}: "
              f"{before:,} -> {after:,} faces")

    print("Done. Point Bozzetto's /create editor at:", args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
