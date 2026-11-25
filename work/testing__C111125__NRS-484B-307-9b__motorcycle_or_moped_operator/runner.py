"""C111125 exact diagnostic preflight; unsourced Native launch is refused."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("C111125 exact case plan changed")
    case_id = config["selected_case_id"]
    if not case_id.startswith(config["assignment_id"] + "__"):
        raise ValueError("C111125 foreign exact case")
    matches = [row for row in json.loads(source)["cases"] if row["case_id"] == case_id]
    if len(matches) != 1 or matches[0]["scenario_parameters"] != config["case_parameters"]:
        raise ValueError("C111125 exact case construction changed")
    if config["fps"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("C111125 original timebase changed")
    expected_views = [("overview", 1920, 1080), ("approach", 1280, 720),
                      ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]
    cameras = config["cameras"]
    if (not isinstance(cameras, list) or
            [(item.get("name"), item.get("width"), item.get("height"))
             for item in cameras] != expected_views or
            any(not item.get("pose_strategy") or not item.get("fov_deg") for item in cameras)):
        raise ValueError("C111125 pinned camera profile changed")
    if config["required_sources"] != ["loaded_map", "official_composite_head", "stopping_reference", "causal_detector_or_malfunction", "participant_tracks", "original_camera_media"]:
        raise ValueError("C111125 required originals changed")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--site-packet", default=os.environ.get("SCENARIO_SITE_PACKET"))
    parser.add_argument("--native-adapter", default=os.environ.get("SCENARIO_NATIVE_ADAPTER"))
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic C111125 case passed: " + case_id)
        return
    if not args.output_dir or not args.site_packet or not args.native_adapter:
        raise ValueError("Reviewed original C111125 map, composite head, detector and camera sources required")
    adapter = importlib.import_module(args.native_adapter)
    if not hasattr(adapter, "open_session"):
        raise ValueError("Operator-owned Native adapter lacks open_session")
    from native_session import capture_events
    try:
        with adapter.open_session(case_id, args.site_packet, args.host, args.port) as session:
            capture_events(session, args.site_packet, case_id, args.output_dir)
        if not session.restoration_verified:
            raise ValueError("Original Native sensor/world restoration unverified")
        from worker_exchange.native_output import seal_capture
        seal_capture(args.output_dir, frames=900,
                     restoration={"restored": True, "scope": "operator adapter closed four sensors and verified unchanged world settings"},
                     errors=[])
    except Exception as error:
        Path(args.output_dir, "native-run-status.json").write_text(json.dumps({
            "errors": [str(error)], "case_id": case_id, "capture_sealed": False}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
