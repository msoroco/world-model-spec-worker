"""Exercise exact-case independent delivery audits on synthetic Native callbacks.

This verifies source binding and rejection behavior. It cannot attest that any
vehicle actually completed the turn or that any actor appears in CARLA pixels.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from construction import POLICIES
from delivery_audit import audit
from native_acquisition import capture
from saved_left_turn import ASSIGNMENT_ID

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))
from test_native_acquisition import Adapter, waypoint


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def reject(call, expected):
    try:
        call()
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f"Expected {expected!r}, got {exc!r}") from exc
        return str(exc)
    raise AssertionError("Invalid delivery evidence was accepted")


def prove(root, suffixes=None, negative_only=False):
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for suffix in (suffixes or POLICIES):
        if suffix not in POLICIES:
            raise ValueError("Unknown exact case suffix: " + suffix)
        case_id = ASSIGNMENT_ID + "__" + suffix
        folder = root / suffix
        folder.mkdir()
        packet = {"map_sha256": "a" * 64, "source_ref": "synthetic-callback-map",
                  "junction_id": 9, "intersection_polygon": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                  "ego_route": [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
                  "opposing_route": [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
                  "ego_blueprint_id": "vehicle.ego", "opponent_blueprint_id": "vehicle.other"}
        map_path = folder / "map.json"
        write(map_path, packet)
        attempt = folder / "attempt"
        capture(adapter=Adapter(), case_id=case_id, map_path=map_path, output=attempt, frame_count=2)
        receipt = json.loads((attempt / "acquisition-receipt.json").read_text(encoding="utf-8"))
        ids = {"ego": 11, "initial_opponent": 12}
        physical = {"case_id": case_id, "trace_sha256": receipt["trace_sha256"],
                    "map_sha256": receipt["map_sha256"], "maneuver_completed": True,
                    "completion_status": "met", "method": "synthetic callback fixture",
                    "reviewer": "CPU test", "original_frame_interval": [100, 101],
                    "participant_actor_ids": ids}
        pixels = {"case_id": case_id, "frame_map_sha256": receipt["frame_map_sha256"],
                  "receipt_sha256": sha(attempt / "acquisition-receipt.json"),
                  "reviewed_frame_count": 2,
                  "reviewed_cameras": ["overview", "approach", "reference_corner", "driver_reference"],
                  "visible_actor_ids": ids, "intersection_boundary_visible": True,
                  "full_duration_reviewed": True, "method": "synthetic callback fixture",
                  "reviewer": "CPU test"}
        physical_path, pixel_path = folder / "physical.json", folder / "pixels.json"
        write(physical_path, physical)
        write(pixel_path, pixels)

        def run(allow=True):
            return audit(attempt=attempt, case_id=case_id, physical_review=physical_path,
                         pixel_review=pixel_path, allow_diagnostic=allow)

        if negative_only:
            # This is the CLI rejection proof expected by the delivery handoff.
            # Preserve the nonzero exit and exact source-specific error in its log.
            run(False)
            raise AssertionError("Diagnostic source unexpectedly accepted")
        valid = run()
        if valid["canonical_delivery_acceptance"] != "unverified" or not valid["diagnostic_fixture"]:
            raise AssertionError("Fixture cannot assert delivery acceptance")
        negatives = {"diagnostic_default": reject(lambda: run(False), "diagnostic fixture")}
        physical["trace_sha256"] = "0" * 64
        write(physical_path, physical)
        negatives["stale_physical"] = reject(run, "physical review is stale")
        physical["trace_sha256"] = receipt["trace_sha256"]
        write(physical_path, physical)
        pixels["visible_actor_ids"] = {"ego": 11}
        write(pixel_path, pixels)
        negatives["missing_actor"] = reject(run, "required actor")
        pixels["visible_actor_ids"] = ids
        write(pixel_path, pixels)
        pixels["frame_map_sha256"] = "0" * 64
        write(pixel_path, pixels)
        negatives["stale_pixels"] = reject(run, "pixel review is stale")
        pixels["frame_map_sha256"] = receipt["frame_map_sha256"]
        write(pixel_path, pixels)
        entries.append({"case_id": case_id, "decoded_images": valid["media_decode"]["decoded_images"],
                        "source_receipt_sha256": sha(attempt / "acquisition-receipt.json"),
                        "negatives": negatives, "physical_acceptance": "unverified",
                        "canonical_delivery_acceptance": "unverified"})
    return {"format": "worker-253-diagnostic-delivery-proof", "assignment_id": ASSIGNMENT_ID,
            "positive_count": len(entries), "negative_count": sum(len(x["negatives"]) for x in entries),
            "cases": entries, "physical_acceptance_claimed": False,
            "canonical_delivery_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--case", choices=[ASSIGNMENT_ID + "__" + key for key in POLICIES])
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    suffixes = [args.case.removeprefix(ASSIGNMENT_ID + "__")] if args.case else None
    result = prove(args.output_root, suffixes, args.negative)
    if args.receipt is not None:
        write(args.receipt, result)
    print(json.dumps({"positive_count": result["positive_count"],
                      "negative_count": result["negative_count"]}))
