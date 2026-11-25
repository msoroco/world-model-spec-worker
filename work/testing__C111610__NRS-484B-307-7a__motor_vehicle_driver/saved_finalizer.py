"""Saved-only exact-case measurement of flashing-arrow participant variants.

The finalizer reads sealed original aspect and actor events. It records region
and movement observations, while leaving lawful presence and yield judgments
for independent source review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_arrow import measure_original, verify_site
from saved_aspect import join_event_history


ASSIGNMENT = "testing__C111610__NRS-484B-307-7a__motor_vehicle_driver"
SUFFIXES = {"arrow_clear", "arrow_ped_crosswalk", "arrow_ped_intersection",
            "arrow_vehicle_intersection", "arrow_concurrent_movement"}


def finalize_saved(site_path: Path, attempt: Path, case_id: str, *,
                   diagnostic: bool = False) -> dict:
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact flashing-arrow case")
    site_path = Path(site_path)
    attempt = Path(attempt)
    site_raw = site_path.read_bytes()
    site = json.loads(site_raw)
    if site.get("case_id") != case_id:
        raise ValueError("reviewed site does not bind exact case")
    if not diagnostic and site.get("source_kind") != "original_native_site_review":
        raise ValueError("original reviewed Native arrow site required")
    verify_site(site, attempt)
    event_receipt = json.loads((attempt / "arrow-event-receipt.json").read_text())
    if (event_receipt.get("format") != "worker-original-arrow-event-v1" or
            event_receipt.get("diagnostic") is not diagnostic):
        raise ValueError("sealed original event receipt required")
    event_ref = event_receipt.get("event_ref")
    if not isinstance(event_ref, dict) or event_ref.get("path") != "arrow-events-original.json":
        raise ValueError("sealed original event source path differs")
    event_path = attempt / event_ref["path"]
    joined = join_event_history(site, attempt, event_ref, delivery=not diagnostic)
    if (joined["original_aspect_sha256"] != event_receipt.get("aspect_sha256") or
            joined["frame_count"] != event_receipt.get("frame_count")):
        raise ValueError("sealed event receipt differs from original arrow sources")
    measured = measure_original(site, attempt, event_ref)
    expected = 3 if diagnostic else 900
    if joined["frame_count"] != measured["frame_count"] or measured["frame_count"] != expected:
        raise ValueError("exact original arrow frame count differs")
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    records = measured["records"]
    present = {(user["kind"], user["region"]) for record in records
               for user in record["other_users"]}
    target = {"arrow_ped_crosswalk": ("pedestrian", "adjacent_crosswalk"),
              "arrow_ped_intersection": ("pedestrian", "intersection"),
              "arrow_vehicle_intersection": ("motor_vehicle", "intersection")}
    if suffix == "arrow_clear" and any(region != "outside" for _, region in present):
        raise ValueError("clear arrow case has a participant in a protected region")
    if suffix in target and target[suffix] not in present:
        raise ValueError("exact arrow participant and region not observed")
    if suffix == "arrow_concurrent_movement":
        events = json.loads(event_path.read_text())
        if not any(row.get("concurrent_indications") and
                   row.get("ego_movement") != site["arrow_movement"] and
                   row.get("concurrent_permission_source") and
                   row.get("ego_movement") == row.get("concurrently_permitted_movement")
                   for row in events):
            raise ValueError("concurrently permitted alternate movement not observed")
    elif any(record["ego_movement"] != site["arrow_movement"] for record in records):
        raise ValueError("ego movement differs from arrow direction")
    return {"format": "c111610-arrow-saved-finalizer-v1", "case_id": case_id,
            "site_sha256": hashlib.sha256(site_raw).hexdigest(),
            "original_aspect_sha256": joined["original_aspect_sha256"],
            "original_event_sha256": joined["original_event_sha256"],
            "frame_count": expected, "observed_arrow_transitions": measured["arrow_transitions"],
            "observed_participant_regions": sorted([list(pair) for pair in present]),
            "event_aspect_join": True, "physical_acceptance": False,
            "lawful_presence_verdict": None, "cautious_entry_verdict": None,
            "right_of_way_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = finalize_saved(args.site, args.attempt, args.case,
                            diagnostic=args.diagnostic)
    if args.output.exists():
        raise ValueError("saved finalizer output already exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
