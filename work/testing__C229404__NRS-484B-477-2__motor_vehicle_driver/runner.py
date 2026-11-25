"""Exact alley parking Native entrypoint; original claims require local review."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from access_measurement import ASSIGNMENT
from native_capture import CAMERAS, capture


def check(root: Path) -> str:
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact alley case plan changed")
    plan = json.loads(plan_bytes)
    case_id = config.get("selected_case_id")
    matching = [row for row in plan["cases"] if row["case_id"] == case_id]
    if len(matching) != 1 or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact alley case missing")
    row = matching[0]
    if (config["assignment_id"], config["law_id"], config["cell_id"],
            config["actor"]) != (ASSIGNMENT, plan["law_id"], plan["cell_id"],
                                plan["actor"]):
        raise ValueError("alley assignment identity differs")
    if (config["access_kind"], config["parking_position"]) != (
            row["access_kind"], row["parking_position"]):
        raise ValueError("exact alley parking condition differs")
    if (config["rate_hz"], config["frame_count"], config["duration_s"]) != (20, 900, 45):
        raise ValueError("alley capture duration or cadence differs")
    if config.get("approach_direction") not in (-1, 1):
        raise ValueError("alley approach direction invalid")
    if set(camera["name"] for camera in config["cameras"]) != CAMERAS:
        raise ValueError("alley four-camera contract differs")
    if config.get("required_atoms") != [] or config.get("source_packets") != []:
        raise ValueError("alley source requirements must remain explicit packets")
    return case_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    case_id = check(root)
    if args.check:
        print("exact alley parking bundle passed: " + case_id)
        return
    if not args.output_dir or not args.output_dir.is_dir():
        raise ValueError("executor output directory required")
    packet = args.packet or os.environ.get("SCENARIO_ALLEY_REVIEWED_PACKET")
    if not packet:
        raise ValueError("reviewed original alley and parcel source packet required")
    from carla_alley_adapter import open_session
    from pipeline_capture import PipelineCapture
    direction = json.loads((root / "config.json").read_text())["approach_direction"]
    session = open_session(case_id, Path(packet), args.host, args.port, direction)
    try:
        session.pipeline_capture = PipelineCapture(session.client, session.ego,
                                                   args.output_dir, case_id)
        capture(session, case_id, args.output_dir / "original-attempt",
                after_tick=session.pipeline_capture.capture)
        from finalize_native import finalize
        finalize(args.output_dir, case_id=case_id, restored=session.restored)
    finally:
        # capture owns brake and teardown after start; a pre-start failure still
        # needs the same cleanup. Session.cleanup raises on failed restoration.
        if not session.closed:
            session.cleanup()


if __name__ == "__main__":
    main()
