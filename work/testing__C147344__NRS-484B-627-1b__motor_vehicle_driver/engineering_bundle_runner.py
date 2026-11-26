"""Exact engineering sweep bundle entrypoint; Native use is source gated."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from engineering_sweep_station import engineering_station


def check_config(config: dict) -> bool:
    case_id = config.get("selected_case_id", "")
    if engineering_station(case_id) is None or config.get("case", {}).get("case_id") != case_id:
        raise ValueError("unassigned exact engineering case")
    if (config.get("rate_hz"), config.get("duration_s"), config.get("diagnostic_only")) != (20, 45, True):
        raise ValueError("engineering capture contract mismatch")
    if set(config.get("cameras", [])) != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four-camera contract mismatch")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    check_config(config)
    if args.check:
        print("engineering sweep construction contract passed")
        return
    if args.output_dir is None:
        raise ValueError("fresh Native output directory required")
    root = os.environ.get("C147344_AUTHORITY_ROOT")
    ref_path = os.environ.get("C147344_SITE_REF")
    if not root or not ref_path:
        raise ValueError("original reviewed site source paths required")
    from engineering_sweep_runner import run
    run(Path(root), json.loads(Path(ref_path).read_text(encoding="utf-8")),
        config["selected_case_id"], args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
