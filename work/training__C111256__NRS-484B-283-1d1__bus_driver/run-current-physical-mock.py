"""Exercise C111256 physical CPU branches on one retained current attempt."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from physical_walk_audit import LIFECYCLE, audit_original, check_lifecycle, classify, diagnostic_source

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion",
                                         "missing_evidence", "lifecycle"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if ROOT / ".runtime-work" not in args.attempt.resolve().parents:
        raise ValueError("Attempt outside .runtime-work")
    manifest = json.loads(args.manifest.read_text())
    case_id = HERE.name + "__" + args.case
    entry = next(row for row in manifest["cases"] if row["case_id"] == case_id)
    base = {"case_id": case_id, "construction_sha256": entry["construction_sha256"],
            "cpu_fixture_mock": True, "mock_input_provenance": "synthetic_native_sample",
            "original_native_motion_verified": False, "original_walk_pixels_verified": False,
            "accepted": False, "legal_verdict_claimed": False}
    if args.kind == "lifecycle":
        events = list(LIFECYCLE)
        if not check_lifecycle(events)["saved_processing_after_owner_release"]:
            raise AssertionError("Lifecycle rejected")
        bad = events.copy()
        bad[-2:] = reversed(bad[-2:])
        try:
            check_lifecycle(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Premature saved processing accepted")
        result = {**base, "events": events, "exit_code": 0,
                  "actual_owner_release_verified": False}
    else:
        source = args.attempt
        names = ("native_samples.jsonl", "video_frames.jsonl", "road_geometry.json")
        samples = rows(source / names[0])
        mapping = rows(source / names[1])
        geometry = json.loads((source / names[2]).read_text())
        if (geometry.get("synthetic_diagnostic") is not True or
                any(row.get("speed_provenance") != "synthetic_native_sample"
                    for row in samples)):
            raise ValueError("Diagnostic source provenance changed")
        if args.case in ("reference", "contrast"):
            if diagnostic_source(source, args.case)["status"] != "met":
                raise ValueError("Diagnostic Walk source incomplete")
            try:
                audit_original(source, args.case, source / "official-walk-review.json")
            except ValueError as error:
                if "Synthetic source cannot prove original Native Walk motion" not in str(error):
                    raise
            else:
                raise AssertionError("Synthetic Walk source accepted as original")
        if args.kind == "incomplete_motion":
            samples = copy.deepcopy(samples)
            for sample in samples:
                sample["pedestrian_body_xy_m"] = [
                    [-5.2, -11.2], [-4.8, -11.2], [-4.8, -10.8], [-5.2, -10.8]]
        elif args.kind == "missing_evidence":
            mapping = mapping[:-1]
        try:
            measured = classify(samples, mapping, geometry, args.case)
            status = measured["status"]
        except ValueError:
            if args.kind != "missing_evidence":
                raise
            measured, status = {}, "unverified"
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if status != expected:
            raise ValueError("Physical fixture status differs: " + args.case + "/" + args.kind)
        result = {**base, "physical_checks": {"maneuver": {
            "status": status, "method": "480-frame synthetic Walk/bus response classifier",
            "sources": list(names)}}, "maneuver_completed": status == "met",
            "realized_observables": measured if status == "met" else {},
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "mock_native_branch_only": True,
            "original_production_audit_rejected": True,
            "source_sha256": {name: sha(source / name) for name in names}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": case_id, "kind": args.kind,
                      "status": result.get("physical_checks", {}).get("maneuver", {}).get("status"),
                      "cpu_fixture_mock": True, "original_native_motion_verified": False}))

if __name__ == "__main__":
    main()
