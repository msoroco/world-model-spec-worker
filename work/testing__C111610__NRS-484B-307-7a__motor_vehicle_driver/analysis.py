"""Saved-only source-bound measurements for one exact flashing-arrow case.

No value here is a lawful-presence, right-of-way or cautiousness verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from native_camera_capture import CAMERAS
from saved_camera_audit import audit as audit_cameras
from saved_finalizer import ASSIGNMENT, finalize_saved


def measure_ego_history(rows: list, *, diagnostic: bool) -> list:
    """Retain original ego motion; never turn an engineering value into a verdict."""
    history = []
    for row in rows:
        values = [row.get("ego_speed_mps"), row.get("ego_brake"),
                  row.get("ego_heading_deg")]
        if all(value is None for value in values) and diagnostic:
            history.append({"frame": row["frame"], "speed_mps": None,
                            "brake": None, "heading_deg": None})
            continue
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in values):
            raise ValueError("original ego kinematic source missing or nonfinite")
        speed, brake, heading = values
        if speed < 0 or not 0 <= brake <= 1:
            raise ValueError("original ego speed or brake range invalid")
        history.append({"frame": row["frame"], "speed_mps": speed,
                        "brake": brake, "heading_deg": heading})
    return history


def report(attempt: Path, *, diagnostic=False, dimensions=None) -> dict:
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    case_id = config["selected_case_id"]
    if config.get("assignment_id") != ASSIGNMENT:
        raise ValueError("exact arrow assignment identity differs")
    if config.get("cameras") != list(CAMERAS):
        raise ValueError("exact four-camera view inventory differs")
    site_path = attempt / "site.json"
    if not site_path.is_file():
        raise ValueError("Missing required source: site.json")
    site = json.loads(site_path.read_text())
    final = finalize_saved(site_path, attempt, case_id, diagnostic=diagnostic)
    camera = audit_cameras(site, attempt, diagnostic=diagnostic,
                           dimensions=dimensions)
    if (camera["original_event_sha256"] != final["original_event_sha256"] or
            camera["original_aspect_sha256"] != final["original_aspect_sha256"] or
            camera["decoded_frames"] != final["frame_count"] or
            camera["decoded_images"] != final["frame_count"] * len(CAMERAS)):
        raise ValueError("saved arrow and camera original sources do not join")
    original_events = json.loads((attempt / "arrow-events-original.json").read_text())
    ego_history = measure_ego_history(original_events, diagnostic=diagnostic)
    camera_receipt = attempt / "arrow-camera-receipt.json"
    sources = {"site.json": hashlib.sha256(site_path.read_bytes()).hexdigest(),
               "arrow-aspect-original.json": final["original_aspect_sha256"],
               "arrow-events-original.json": final["original_event_sha256"],
               "arrow-camera-receipt.json": hashlib.sha256(camera_receipt.read_bytes()).hexdigest()}
    source_inventory = {ref["path"]: ref["sha256"] for ref in site["original_sources"]}
    source_inventory.update({name + ".png.zip": ref["sha256"] for name, ref in
                             json.loads(camera_receipt.read_text())["camera_sources"].items()})
    observations = {
        "arrow_display_observation": {"frame_count": final["frame_count"],
            "observed_arrow_transitions": final["observed_arrow_transitions"]},
        "ego_movement_observation": {"event_aspect_join": final["event_aspect_join"],
            "case_id": case_id, "ego_kinematics": ego_history},
        "participant_region_observation": {"observed_regions": final["observed_participant_regions"]},
        "camera_decode_observation": {"decoded_frames": camera["decoded_frames"],
            "decoded_images": camera["decoded_images"]},
    }
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {key: {"value": value, "method": "report",
                                   "sources": sources} for key, value in observations.items()},
            "source_inventory": source_inventory,
            "analysis_complete": True, "legal_verdict_claimed": False,
            "physical_acceptance": False,
            "limitations": ["Original signal and actor source review remains necessary.",
                            "Physical pixel visibility, cautiousness, lawful presence and right of way remain unconfirmed."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--diagnostic-width", type=int)
    parser.add_argument("--diagnostic-height", type=int)
    args = parser.parse_args()
    dimensions = None
    if args.diagnostic:
        if not args.diagnostic_width or not args.diagnostic_height:
            raise ValueError("diagnostic camera dimensions required")
        dimensions = {name: (args.diagnostic_width, args.diagnostic_height)
                      for name in CAMERAS}
    elif args.diagnostic_width or args.diagnostic_height:
        raise ValueError("diagnostic camera dimensions cannot be used in delivery")
    value = report(args.attempt, diagnostic=args.diagnostic,
                   dimensions=dimensions)
    if args.output.exists():
        raise ValueError("analysis output already exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2) + "\n")


if __name__ == "__main__":
    main()
