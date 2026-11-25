"""Exact intersection capture through a reviewed operator-owned adapter."""
import argparse
import hashlib
import importlib
import json
import os
import signal
from pathlib import Path
from saved_delivery import CAMERAS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan changed")
    plan = json.loads(plan_bytes)
    case = config["selected_case_id"]
    entries = [row for row in plan["cases"] if row["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case absent")
    row = entries[0]
    for field in ("requested_front_body_gap_ft", "activity", "halt_cause"):
        if row[field] != config[field]:
            raise ValueError("Exact requested condition changed: " + field)
    if (config["law_id"], config["cell_id"], config["actor"]) != (plan["law_id"], plan["cell_id"], plan["actor"]):
        raise ValueError("Assignment identity changed")
    if (config["rate_hz"], config["frame_count"], config["duration_s"]) != (20, 900, 45):
        raise ValueError("Original capture interval changed")
    if config["cameras"] != list(CAMERAS):
        raise ValueError("Original four-camera contract changed")
    if config["source_requirements"] != ["reviewed_map_packet", "original_actor_pose", "original_context", "four_original_camera_png_streams"]:
        raise ValueError("Original source contract changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--map-packet")
    parser.add_argument("--adapter")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic exact intersection bundle passed: " + case)
        return
    packet_path = args.map_packet or os.environ.get("SCENARIO_INTERSECTION_MAP_PACKET")
    adapter_name = args.adapter or os.environ.get("SCENARIO_INTERSECTION_ADAPTER", "native_adapter")
    if not args.output_dir or not packet_path:
        raise ValueError("Reviewed map packet required for original Native capture")
    fallback_role = json.loads((Path(__file__).resolve().parent / "config.json").read_text()).get("fallback_route_role")
    if fallback_role:
        packet = json.loads(Path(packet_path).read_text())
        if packet.get("reviewed_route_role") != fallback_role:
            raise ValueError("Fallback requires a separately reviewed alternate approach packet")
    from native_bundle import capture_bundle
    from finalize_capture import publish
    from pipeline_capture import PipelineCapture
    adapter = importlib.import_module(adapter_name)
    if not hasattr(adapter, "open_session"):
        raise ValueError("Native adapter lacks owned open_session")
    output_dir = Path(args.output_dir)
    if not output_dir.is_dir():
        raise ValueError("Executor output directory missing")
    attempt_dir = output_dir / "original-attempt"
    if attempt_dir.exists():
        raise ValueError("Original Native attempt already exists")
    def terminate(_signal, _frame):
        raise SystemExit("Original Native capture interrupted")
    signal.signal(signal.SIGTERM, terminate)
    with adapter.open_session(case, packet_path, args.host, args.port) as session:
        with PipelineCapture(session.client, session.ego, output_dir, case) as native_capture:
            capture_bundle(
                session.world, session.ego, attempt_dir,
                map_packet_path=packet_path, case_id=case,
                attempt_id=session.attempt_id, recording_id=session.recording_id,
                world_to_local=session.world_to_local, read_camera=session.read_camera,
                read_context=session.read_context, acquisition_kind="original_native",
                native_capture=native_capture)
    publish(output_dir, case_id=case,
            restoration={"restored": session.restored,
                         "method": "owned actor and sensor teardown plus settings readback"},
            require_pipeline=True)


if __name__ == "__main__":
    main()
