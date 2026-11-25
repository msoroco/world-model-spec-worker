"""Exact sidewalk-bypass source-gated Native bundle entrypoint."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from geometry import construct, audit_design
from native_walking import FPS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    plan_data = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_data).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan changed")
    case = config["selected_case_id"]
    entries = [x for x in json.loads(plan_data)["cases"] if x["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case missing")
    if config["construction_parameters"] != entries[0]["construction_parameters"]:
        raise ValueError("Case parameters changed")
    if config["rate_hz"] != FPS or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original frame contract changed")
    cameras = [item.get("name") if isinstance(item, dict) else item for item in config["cameras"]]
    if cameras != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Four-camera contract changed")
    p = config["construction_parameters"]
    scene = construct(case, direction=p["direction"], area_blocked=p["area_blocked"],
                      sidewalk_end=float(p["sidewalk_end_m"]), obstruction_kind=p["obstruction_kind"])
    result = audit_design(scene)
    if result["designated_lane_used"] != p["area_blocked"]:
        raise ValueError("Bicycle-lane condition changed")
    if p["obstruction_kind"] == "missing_section" and not scene.missing_sections:
        raise ValueError("Missing sidewalk surface not constructed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("source-gated sidewalk-bypass bundle passed: " + case)
        return
    if not args.output_dir or not args.host or not args.port:
        raise ValueError("Native output and host/port required")
    source_name = os.environ.get("SCENARIO_PEDESTRIAN_SOURCE_ROOT")
    if not source_name:
        raise ValueError("reviewed original hill-crest source root required")
    source = Path(source_name).resolve()
    output = Path(args.output_dir).resolve()
    if not source.is_dir() or not output.is_dir() or source == output:
        raise ValueError("reviewed source/output roots invalid")
    names = ("site-survey.json", "camera-profile.json", "traffic-plan.json")
    for name in names:
        original = source / name
        target = output / name
        if not original.is_file() or target.exists():
            raise ValueError("missing or colliding original source: " + name)
        shutil.copyfile(original, target)
        if hashlib.sha256(original.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise ValueError("original source changed while copying")
    survey = json.loads((output / "site-survey.json").read_text())
    review = survey.get("reviewed_original_site", {})
    refs = review.get("source_refs", []) if isinstance(review, dict) else []
    if not refs or not all(isinstance(ref, dict) and ref.get("path") and ref.get("sha256") for ref in refs):
        raise ValueError("original hill-crest site review lacks source hashes")
    for ref in refs:
        relative = Path(ref["path"])
        original = (source / relative).resolve()
        target = (output / relative).resolve()
        if relative.is_absolute() or not original.is_relative_to(source) or not target.is_relative_to(output):
            raise ValueError("original site review source path escapes root")
        if not original.is_file() or target.exists():
            raise ValueError("missing or colliding original site review source")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("original site review source bytes differ")
    import carla
    from native_bound_attempt import run_bound_attempt
    from native_publication import publish_original
    from worker_exchange import world_restore
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    plan = json.loads((output / "case-plan.json").read_text())
    run_bound_attempt(client, carla, plan, case, output / names[0],
                      output / names[1], output / names[2], output,
                      restore_api=world_restore,
                      walking_speed_m_s=json.loads((Path(__file__).resolve().parent / "config.json").read_text())["requested_speed_mps"])
    publish_original(output, case)


if __name__ == "__main__":
    main()
