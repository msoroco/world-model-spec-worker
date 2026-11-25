"""Exact source-gated Native entrypoint for one materialized 287-1c case."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from delivery_audit import CASES
from native_observation import CAMERA_DIMENSIONS
from reviewed_site import load_reviewed_site


def check(directory: str | Path) -> dict:
    root = Path(directory).resolve()
    config = json.loads((root / "config.json").read_text())
    spec = json.loads((root / "case-spec.json").read_text())
    controller = json.loads((root / "controller.json").read_text())
    case_id = config.get("selected_case_id")
    if case_id not in CASES or spec.get("case_id") != case_id or \
       (config.get("law_id"), config.get("cell_id"), config.get("actor")) != \
       ("NRS-484B-287-1c", "C111329", "pedestrian"):
        raise ValueError("materialized exact case identity differs")
    cameras = config.get("cameras", [])
    actual_cameras = {item.get("name"): [item.get("width"), item.get("height")]
                      for item in cameras if isinstance(item, dict)}
    if (config.get("rate_hz"), config.get("duration_s")) != (20, 45) or \
       len(cameras) != 4 or actual_cameras != \
       {name: list(dimensions) for name, dimensions in CAMERA_DIMENSIONS.items()}:
        raise ValueError("materialized original capture profile differs")
    marked, operating = CASES[case_id]
    if spec.get("marked_crosswalk_present") is not marked or \
       spec.get("both_devices_operating") is not operating:
        raise ValueError("materialized exact case distinction differs")
    speed = controller.get("walker_speed_mps")
    if type(speed) not in (int, float) or not 0 < speed <= 3:
        raise ValueError("positive pedestrian controller speed required")
    return {"case_id": case_id, "walker_speed_mps": float(speed),
            "source_gate": "reviewed original C111329 site required before Native"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--site-review", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    selected = check(args.output_dir)
    if args.check:
        print(json.dumps({**selected, "static_construction_valid": True,
                          "native_started": False}))
        return 0
    source = args.site_review or os.environ.get("C111329_287_1C_SITE_REVIEW")
    if not source:
        raise ValueError("Missing required source: reviewed original C111329 site packet")
    load_reviewed_site(source, expected_case_id=selected["case_id"])
    from native_entry import run_native
    result = run_native(source, selected["case_id"], args.output_dir,
        host=args.host, port=args.port,
        controller_speed_mps=selected["walker_speed_mps"])
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
