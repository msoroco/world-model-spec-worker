"""Replay one selected crosswalk CPU branch without original Native claims."""
import argparse
import hashlib
import json
from pathlib import Path

from physical_outcome_audit import audit as audit_original, classify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lifecycle(events, exit_code):
    if events != EVENTS or exit_code != 0:
        raise ValueError("Saved analysis preceded Native owner release")
    return {"events": EVENTS, "exit_code": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=("reference", "contrast"))
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    case_id = HERE.name + "__" + args.case
    entry = next(x for x in manifest["cases"] if x["case_id"] == case_id)
    if args.kind == "lifecycle":
        result = lifecycle(EVENTS, 0)
        for events, code in ((EVENTS[-1:] + EVENTS[:-1], 0), (EVENTS, 1)):
            try:
                lifecycle(events, code)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid lifecycle accepted")
        result.update(cpu_fixture_mock=True, original_owner_release_verified=False)
    else:
        source = ROOT / ".runtime-work" / f"c10316-current-{args.case}-primary-compat"
        native = source / "native_samples.jsonl"
        mapping = source / "video_frames.jsonl"
        context_path = source / "crosswalk-context.json"
        evidence_path = source / "capture/evidence.jsonl"
        samples = [json.loads(x) for x in native.read_text().splitlines()]
        frames = [json.loads(x) for x in mapping.read_text().splitlines()]
        evidence = [json.loads(x) for x in evidence_path.read_text().splitlines()]
        context = json.loads(context_path.read_text())
        if (len(samples) != len(evidence) or len(samples) != 240 or
                context["source_kind"] != "synthetic_scene_request" or
                not all(x["ego"].get("speed_provenance") == "synthetic_native_sample"
                        for x in evidence)):
            raise ValueError("Selected synthetic crosswalk provenance missing")
        try:
            audit_original(source, case_id)
        except ValueError as error:
            if "Synthetic or unsealed" not in str(error):
                raise
        else:
            raise AssertionError("Synthetic crosswalk accepted as original")
        expected_half = "right" if args.case == "reference" else "left"
        if args.kind == "incomplete_motion":
            expected_half = "left" if expected_half == "right" else "right"
        if args.kind == "missing_evidence":
            samples = samples[:-1]
        try:
            measured = classify(samples, frames, context, expected_half)
            status = measured["status"]
        except ValueError:
            measured = {}
            status = "unverified"
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if status != expected:
            raise AssertionError("Crosswalk CPU branch differs: " + args.case + " " + args.kind)
        result = {"physical_checks": {"maneuver": {
                    "status": status,
                    "method": "240-frame source-shaped crosswalk footprint and half classification",
                    "sources": ["native_samples.jsonl", "video_frames.jsonl", "crosswalk-context.json"]}},
                  "maneuver_completed": status == "met",
                  "realized_observables": measured if status == "met" else {},
                  "provenance_kind": "native", "diagnostic_fixture": False,
                  "cpu_fixture_mock": True, "mock_native_branch_only": True,
                  "mock_input_provenance": "synthetic_native_sample",
                  "original_native_motion_verified": False,
                  "original_production_audit_rejected": True,
                  "practicability_verified": False, "accepted": False,
                  "legal_verdict_claimed": False,
                  "retained_source_sha256": {"native_samples.jsonl": sha(native),
                                             "video_frames.jsonl": sha(mapping),
                                             "crosswalk-context.json": sha(context_path),
                                             "capture/evidence.jsonl": sha(evidence_path)}}
    result["construction_sha256"] = entry["construction_sha256"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": case_id, "kind": args.kind,
                      "status": result.get("physical_checks", {}).get("maneuver", {}).get("status"),
                      "cpu_fixture_mock": True, "original_native_motion_verified": False}))


if __name__ == "__main__":
    main()
