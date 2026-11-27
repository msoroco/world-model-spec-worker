"""Exact materialized-case entrypoint for C177626 Native entry drafts."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
_spec = importlib.util.spec_from_file_location(
    "_c177626_native_runner", Path(__file__).resolve().parent / "native/runner.py")
_native = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_native)
native_check, native_execute = _native.check, _native.execute


def check(config):
    if config.get("assignment_id") != "training__C177626__NRS-484B-263__motor_vehicle_driver":
        raise ValueError("exact assignment identity differs")
    if config.get("law_id") != "NRS-484B-263" or config.get("cell_id") != "C177626":
        raise ValueError("frozen law/cell identity differs")
    if config.get("actor") != "motor_vehicle_driver":
        raise ValueError("frozen actor identity differs")
    if config.get("frames") != 600 or config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("exact camera and duration plan differs")
    return native_check(config["case_id"], config["candidate_id"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
    proposal = check(config)
    if args.check:
        print(json.dumps(proposal, allow_nan=False))
    else:
        if args.output_dir is None or args.host is None or args.port is None:
            raise ValueError("explicit owned Native endpoint and output required")
        native_execute(config["case_id"], config["candidate_id"],
                       args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
