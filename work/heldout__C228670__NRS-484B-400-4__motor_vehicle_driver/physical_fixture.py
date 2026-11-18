"""CPU-only turn geometry outcome fixtures from the exact diagnostic sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from turn_geometry import measure

HERE = Path(__file__).resolve().parent


def run(case_id: str, kind: str) -> dict:
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next((x for x in manifest["cases"] if x["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("unknown exact turn case")
    slug = case_id.rsplit("__", 1)[-1]
    diagnostic_path = HERE / f"diagnostic-{slug}.json"
    diagnostic = json.loads(diagnostic_path.read_text())
    files = diagnostic["files"]
    source_names = ("road_geometry.json", "body_footprints.json", "body_footprints.jsonl",
                    "video_frames.jsonl", "trace.jsonl")
    hashes = {name: hashlib.sha256(files[name].encode()).hexdigest() for name in source_names}
    with TemporaryDirectory(prefix="turn-physical-") as temp:
        base = Path(temp)
        geometry = base / "road_geometry.json"
        body = base / "body_footprints.json"
        geometry.write_text(files["road_geometry.json"])
        body.write_text(files["body_footprints.json"])
        measured = measure(geometry, body)
        expected_right = slug.endswith("depart_right")
        if measured["departure_all_corners_right_of_centerline"] != expected_right:
            raise ValueError("complete source has the wrong departure side")
        if kind == "complete_motion":
            status = "met"
        elif kind == "incomplete_motion":
            # Suppress the departure phase to test rejection of an unfinished turn.
            changed = json.loads(body.read_text())
            for row in changed["frames"]:
                if row.get("phase") == "leaving_intersection":
                    row["phase"] = "turning"
            body.write_text(json.dumps(changed))
            try:
                measure(geometry, body)
            except ValueError as error:
                if "approach and leaving-intersection phases absent" not in str(error):
                    raise
            else:
                raise ValueError("incomplete turn was accepted")
            status = "not_met"
        elif kind == "missing_evidence":
            body.unlink()
            try:
                measure(geometry, body)
            except ValueError as error:
                if "missing required geometry source" not in str(error):
                    raise
            else:
                raise ValueError("missing body evidence was accepted")
            status = "unverified"
        else:
            raise ValueError("unknown fixture kind")
    construction = HERE / entry["construction"]
    return {
        "format": "worker-physical-fixture-outcome", "case_id": case_id,
        "fixture_kind": kind, "fixture_only": True, "diagnostic_fixture": True,
        "actual_native_capture": False, "provenance_kind": "synthetic_fixture",
        "provenance_note": "Synthetic source protocol only; no CARLA acquisition or legal conclusion",
        "physical_checks": {"maneuver": {
            "status": status,
            "method": "original map and four-corner body geometry; incomplete and absent phase perturbations",
            "sources": {"construction": entry["construction"],
                        "construction_sha256": hashlib.sha256(construction.read_bytes()).hexdigest(),
                        "diagnostic": str(diagnostic_path.relative_to(HERE.parent.parent)),
                        "diagnostic_sha256": hashlib.sha256(diagnostic_path.read_bytes()).hexdigest(),
                        "source_sha256": hashes,
                        "perturbation": kind},
            "missing_evidence": ["body_footprints.json"] if kind == "missing_evidence" else []}},
        "maneuver_completed": status == "met",
        "realized_observables": ({
            "approach_left_curb_nearest_m": measured["approach_left_curb_nearest_m"],
            "departure_centerline_min_signed_m": measured["departure_centerline_min_signed_m"],
            "departure_centerline_max_signed_m": measured["departure_centerline_max_signed_m"],
            "departure_all_corners_right_of_centerline": measured["departure_all_corners_right_of_centerline"]
        } if status == "met" else {}),
        "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    outcome = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "status": outcome["physical_checks"]["maneuver"]["status"],
                      "diagnostic_fixture": True}))
