"""Exact C183394 original Native acquisition entrypoint."""
import argparse
import json
from pathlib import Path

from beam_capture import run
from beam_scene import MODES, request, validate_request


def check(bundle):
    bundle = Path(bundle).resolve()
    config = json.loads((bundle / "config.json").read_text())
    case_id = config["selected_case_id"]
    suffix = case_id.rsplit("__", 1)[-1]
    if suffix not in MODES or config["beam_mode"] != MODES[suffix]:
        raise ValueError("Exact beam mode differs from selected case")
    if case_id not in config["supported_case_ids"] or config["cell_id"] != "C183394" \
            or config["law_id"] != "NRS-484D-215-1" \
            or config["actor"] != "motor_vehicle_driver":
        raise ValueError("Frozen beam identity differs")
    if config["rate_hz"] != 20 or config["duration_s"] != 30 or \
            not 0 < config["acceleration_gain"] <= .5:
        raise ValueError("Beam acquisition timing or controller differs")
    plan = request(suffix)
    validate_request(plan)
    return {"case_id": case_id, "frames": 600, "camera_count": 4,
            "native_imported": False, "physical_success_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    print(json.dumps(check(bundle), sort_keys=True))
    if not args.check:
        if not args.output_dir:
            parser.error("--output-dir is required for Native capture")
        run(bundle, args.output_dir, args.host, args.port)
