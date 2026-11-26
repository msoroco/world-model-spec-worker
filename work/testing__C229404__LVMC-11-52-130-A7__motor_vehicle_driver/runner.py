"""Exact LVMC driveway bundle entrypoint; Native sources are supplied locally."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from driveway_measurements import ASSIGNMENT_ID


ROOT = Path(__file__).resolve().parent


def check(root=ROOT):
    root = Path(root)
    config = json.loads((root / "config.json").read_text())
    raw = (root / "case-plan.json").read_bytes()
    plan = json.loads(raw)
    if hashlib.sha256(raw).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact LVMC driveway plan changed")
    if (config.get("assignment_id"), config.get("law_id"), config.get("cell_id"),
            config.get("actor")) != (ASSIGNMENT_ID, plan["law_id"], plan["cell_id"],
                                     plan["actor"]):
        raise ValueError("LVMC assignment identity differs")
    matches = [row for row in plan["cases"] if row["case_id"] == config.get("selected_case_id")]
    if len(matches) != 1:
        raise ValueError("selected exact driveway case absent")
    row = matches[0]
    for key in ("driveway_kind", "activity", "position_target", "driver_relationship",
                "necessity_or_postal_context"):
        if config.get(key) != row[key]:
            raise ValueError("selected LVMC case condition differs: " + key)
    if (config.get("rate_hz"), config.get("duration_s"), config.get("frame_count")) != (20, 45, 900):
        raise ValueError("selected driveway capture contract differs")
    if config.get("approach_direction") not in (-1, 1):
        raise ValueError("selected driveway direction differs")
    if config.get("required_atoms") != [] or config.get("source_packets") != []:
        raise ValueError("original source packets must stay explicit")
    return config["selected_case_id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("exact LVMC driveway bundle passed: " + case_id)
        return
    packet = args.packet or os.environ.get("LVMC_DRIVEWAY_REVIEWED_PACKET")
    if not packet or not args.output_dir:
        raise ValueError("reviewed original driveway packet and output directory required")
    from native_driveway import capture
    config = json.loads((ROOT / "config.json").read_text())
    capture(case_id, packet, args.output_dir / "original-attempt", host=args.host,
            port=args.port, approach_direction=config["approach_direction"])
    from finalize_native import finalize
    finalize(args.output_dir, case_id)


if __name__ == "__main__":
    main()
