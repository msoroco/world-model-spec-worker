"""Exact C111304 encounter bundle preflight; no unsourced simulation."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from encounter import CASES
from native_acquisition import CAMERAS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan source changed")
    case_id = config["selected_case_id"]
    if not case_id.startswith(config["assignment_id"] + "__"):
        raise ValueError("Foreign exact case")
    if sum(row["case_id"] == case_id for row in json.loads(source)["cases"]) != 1:
        raise ValueError("Exact case absent from plan")
    suffix = case_id.removeprefix(config["assignment_id"] + "__")
    matches = [case for case in CASES if case.case_id == suffix]
    if len(matches) != 1 or config["case_spec"] != asdict(matches[0]):
        raise ValueError("Exact encounter construction changed")
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original timebase changed")
    if config["cameras"] != list(CAMERAS):
        raise ValueError("Original four-camera plan changed")
    if config["required_sources"] != ["loaded_map", "public_access_review", "site_packet", "actor_trace", "control_trace", "original_camera_media"]:
        raise ValueError("Required original sources changed")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic C111304 encounter bundle passed: " + case_id)
        return
    sources = [os.environ.get(name) for name in (
        "C111304_SITE_SOURCE", "C111304_ACCESS_SOURCE",
        "C111304_ACCESS_REVIEW", "C111304_CAMERA_PLAN")]
    if not all(sources):
        raise ValueError("Reviewed original C111304 site source environment required")
    if not args.output_dir:
        raise ValueError("Existing Native attempt --output-dir required")
    import carla
    from native_runner import run
    config = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
    client = carla.Client(args.host, args.port)
    client.set_timeout(20.0)
    print(json.dumps(run(client.get_world(), carla,
                         case_id.removeprefix(config["assignment_id"] + "__"),
                         *(Path(value) for value in sources), Path(args.output_dir),
                         client=client),
                     sort_keys=True))


if __name__ == "__main__":
    main()
