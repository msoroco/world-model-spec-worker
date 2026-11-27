"""Exact alley operation diagnostic entrypoint."""
import argparse
import hashlib
import json
import importlib
import os
from pathlib import Path
from alley_geometry import validate
from native_operation import CASE_PROFILES
from native_capture import CAMERAS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    scene_bytes = (root / "alley-scene.json").read_bytes()
    if hashlib.sha256(scene_bytes).hexdigest() != config["scene_sha256"]:
        raise ValueError("alley scene source changed")
    scene = json.loads(scene_bytes)
    if config["selected_case_id"] not in CASE_PROFILES:
        raise ValueError("unknown exact alley case")
    if config["profile"] != CASE_PROFILES[config["selected_case_id"]]:
        raise ValueError("case controller profile differs")
    if config["fps"] != 20 or config["duration_s"] != 45:
        raise ValueError("original acquisition duration differs")
    if config["native_camera_ids"] != list(CAMERAS) or [item["name"] for item in config["cameras"]] != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("original camera identities differ")
    validate(scene)
    return config["selected_case_id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--site-packet")
    parser.add_argument("--attention-packet")
    parser.add_argument("--adapter")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic alley bundle passed: " + case)
        return
    site_packet = args.site_packet or os.environ.get("SCENARIO_NATIVE_SITE_PACKET")
    attention_packet = args.attention_packet or os.environ.get("SCENARIO_NATIVE_ATTENTION_PACKET")
    adapter_name = args.adapter or os.environ.get("SCENARIO_NATIVE_ADAPTER")
    if not args.output_dir or not site_packet or not attention_packet or not adapter_name:
        raise ValueError("Reviewed Native site, interior attention and original camera source required; diagnostic capture refused")
    adapter = importlib.import_module(adapter_name)
    if not hasattr(adapter, "open_session"):
        raise ValueError("Operator-owned Native adapter lacks open_session")
    from owned_runner import capture_reviewed
    try:
        with adapter.open_session(case, site_packet, args.host, args.port) as session:
            capture_reviewed(session, site_packet, case, args.output_dir,
                             attention_packet_path=attention_packet)
        from runtime_publication import seal_reviewed
        seal_reviewed(Path(args.output_dir), getattr(session, "restoration_receipt", None))
    except Exception as error:
        status = Path(args.output_dir) / "native-run-status.json"
        if not status.exists():
            status.write_text(json.dumps({"case_id": case, "errors": [str(error)],
                                          "capture_sealed": False,
                                          "physical_acceptance_claimed": False}) + "\n")
        raise


if __name__ == "__main__":
    main()
