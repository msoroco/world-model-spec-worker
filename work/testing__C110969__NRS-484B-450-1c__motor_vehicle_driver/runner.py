"""Exact case identity and source-profile preflight."""
import argparse
import hashlib
import json
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("exact intersection plan source changed")
    plan = json.loads(source)
    case = config["selected_case_id"]
    if not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("foreign intersection case")
    matches = [row for row in plan["cases"] if row["case_id"] == case]
    if len(matches) != 1:
        raise ValueError("exact intersection case absent")
    row = matches[0]
    for key in ("activity_intent", "body_destination", "exception_context"):
        if row[key] != config[key]:
            raise ValueError("exact intersection case intent changed: " + key)
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("original intersection interval changed")
    if config["camera_dimensions"] != {"overview": [1920, 1080], "approach": [1280, 720],
                                       "reference_corner": [1280, 720], "driver_reference": [1280, 720]}:
        raise ValueError("original four-camera profile changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic intersection construction passed: " + case)
        return
    if not args.output_dir:
        raise ValueError("Native attempt output directory required")
    from native_capture_entrypoint import run_from_environment
    result = run_from_environment(case, args.output_dir, args.host, args.port)
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
