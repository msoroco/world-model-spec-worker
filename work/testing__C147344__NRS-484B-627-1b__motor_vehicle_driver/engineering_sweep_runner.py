"""Run one bounded speed sampling case on a reviewed local Native site."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engineering_sweep_station import plan_engineering
from reviewed_scene import ASSIGNMENT, execute_native


def run(authority_root: Path, site_ref: dict, case_id: str,
        output_dir: Path, host: str, port: int) -> None:
    authority_root = Path(authority_root).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists() or output_dir.is_relative_to(authority_root):
        raise ValueError("fresh sweep attempt outside reviewed authority root required")
    scene = plan_engineering(authority_root, site_ref, case_id)
    site = json.loads((authority_root / site_ref["path"]).read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True)
    (output_dir / "requested-scene.json").write_text(
        json.dumps(scene, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    from sweep_native_adapter import SweepNativeAdapter

    adapter = SweepNativeAdapter(host, port, output_dir)
    adapter.site_road_id = site["road_id"]
    adapter.assignment_id = ASSIGNMENT
    adapter.case_id = case_id
    adapter.trace_id = output_dir.name
    adapter.rightmost_lane_id = scene["rightmost_lane_id"]
    adapter.marked_lane_count = len(site["same_direction_lanes"])
    try:
        execute_native(scene, adapter)
    finally:
        adapter.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--site-ref", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    run(args.authority_root, json.loads(args.site_ref.read_text(encoding="utf-8")),
        args.case_id, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
