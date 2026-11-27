"""Exact protected-lane Native entrypoint; original reviewed packet required."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scene_review import reviewed_scene

ROOT = Path(__file__).resolve().parent
AID = "testing__C147339__NRS-486-341__motor_vehicle_driver"


def config():
    value = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if (value.get("assignment_id") != AID or
            not value.get("selected_case_id", "").startswith(AID + "__") or
            value.get("law_id") != "NRS-486-341" or value.get("cell_id") != "C147339" or
            value.get("actor") != "motor_vehicle_driver" or
            value.get("rate_hz") != 20 or value.get("duration_s") != 45):
        raise ValueError("frozen protected-lane case or capture contract differs")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    value = config()
    if args.check:
        print(json.dumps({"case_id": value["selected_case_id"],
                          "reviewed_original_scene_required": True,
                          "capture_contract_checked": True}))
        return 0
    if not args.output_dir:
        parser.error("--output-dir required")
    packet = os.environ.get("C147339_REVIEWED_SCENE_PACKET")
    if not packet:
        raise ValueError("C147339_REVIEWED_SCENE_PACKET original reviewed packet required")
    path = Path(packet).resolve()
    scene = reviewed_scene(path, value["selected_case_id"])
    from original_capture import run_native
    run_native(value, scene, path, Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
