"""Source-bound synthetic CPU checks of alley stopping and owner closure."""
import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(rows, source_sha, case_id):
    complete = len(rows) == 600 and all(
        row.get("case_id") == case_id and
        row.get("diagnostic_fixture_only") is True and
        row.get("source_kind") == "original_native_observation" and
        row.get("frame") == index and
        row.get("alley_boundary_source_id") and
        row.get("position_xyz_m") == [1, 0, 0] and
        row.get("velocity_xyz_mps") == [0, 0, 0]
        for index, row in enumerate(rows))
    if not rows or len(rows) != 600 or any(
            row.get("frame") != index for index, row in enumerate(rows)):
        status = "unverified"
    else:
        status = "met" if complete else "not_met"
    return {
        "case_id": case_id,
        "physical_checks": {"maneuver": {
            "status": status,
            "method": "600 frame original-shaped alley position and velocity join; synthetic CPU fixture only",
            "sources": {"alley-native.jsonl": source_sha},
            "observed": {"frame_count": len(rows),
                         "stopped_in_alley_frames": sum(
                             row.get("position_xyz_m") == [1, 0, 0] and
                             row.get("velocity_xyz_mps") == [0, 0, 0]
                             for row in rows)}}},
        "maneuver_completed": status == "met",
        "realized_observables": {"stopped_in_alley_frames": 600}
        if status == "met" else {},
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "physical_acceptance_claimed": False,
        "legal_result": None,
    }


def lifecycle(events, exit_code):
    if events != EVENTS or exit_code != 0:
        raise ValueError("Saved processing requires ordered owner release")
    return {"events": events, "exit_code": exit_code,
            "original_owner_release_verified": False,
            "cpu_fixture_mock": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion",
                                 "missing_evidence", "lifecycle"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((PACKAGE / "selected-draft-manifest.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    if args.kind == "lifecycle":
        result = lifecycle(EVENTS, 0)
        for events, code in ((list(reversed(EVENTS)), 0), (EVENTS, 1)):
            try:
                lifecycle(events, code)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid owner release sequence accepted")
    else:
        suffix = args.case.rsplit("__", 1)[-1]
        source = PACKAGE / "native/diagnostic" / suffix / "sources/alley-native.jsonl"
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if args.kind == "incomplete_motion":
            for row in rows[-30:]:
                row["velocity_xyz_mps"] = [1, 0, 0]
        elif args.kind == "missing_evidence":
            rows.pop()
        result = classify(rows, sha(source), args.case)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise AssertionError("Physical CPU branch differs")
    result["construction_sha256"] = entry["construction_sha256"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "cpu_fixture_mock": True}))


if __name__ == "__main__":
    main()
