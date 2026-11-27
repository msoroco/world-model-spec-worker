"""Exact residential driveway Native entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def check(root):
    root = Path(root)
    config = json.loads((root / "config.json").read_text())
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact driveway case plan changed")
    plan = json.loads(plan_bytes)
    case_id = config.get("selected_case_id")
    cases = [c for c in plan["cases"] if c["case_id"] == case_id]
    if len(cases) != 1 or case_id not in config.get("supported_case_ids", []):
        raise ValueError("exact driveway case missing")
    if (config.get("assignment_id"), config.get("law_id"), config.get("cell_id"),
            config.get("actor")) != (plan["assignment_id"], plan["law_id"],
                                     plan["cell_id"], plan["actor"]):
        raise ValueError("driveway assignment identity differs")
    if config.get("case") != cases[0]:
        raise ValueError("selected driveway case definition differs")
    if (config.get("rate_hz"), config.get("frame_count"), config.get("duration_s")) != (20, 900, 45):
        raise ValueError("driveway capture duration or cadence differs")
    profile = (("overview", 1920, 1080), ("approach", 1280, 720),
               ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
    if [(c.get("name"), c.get("width"), c.get("height")) for c in config.get("cameras", [])] != list(profile):
        raise ValueError("driveway four-camera profile differs")
    if config.get("required_atoms") != [] or config.get("source_packets") != []:
        raise ValueError("driveway original observations must remain sourced packets")
    return cases[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    case = check(root)
    if args.check:
        print("exact driveway bundle passed: " + case["case_id"])
        return
    if not args.output_dir or not args.output_dir.is_dir():
        raise ValueError("executor output directory required")
    packet = args.packet or os.environ.get("SCENARIO_REVIEWED_DRIVEWAY_PACKET")
    if not packet:
        raise ValueError("reviewed original residence-district driveway packet required")
    from carla_driveway_adapter import open_session
    from native_acquisition import capture
    from pipeline_capture import PipelineCapture
    session = open_session(case, Path(packet), args.host, args.port)
    try:
        session.pipeline_capture = PipelineCapture(session.client, session.actors["ego"],
                                                   args.output_dir, case["case_id"])
        capture(session, case, args.output_dir / "original-attempt",
                after_tick=session.pipeline_capture.capture)
        session.capture_complete = True
        from finalize_native import finalize
        finalize(args.output_dir, case_id=case["case_id"], restored=session.restored)
    finally:
        if not session.closed:
            session.cleanup()


if __name__ == "__main__":
    main()
