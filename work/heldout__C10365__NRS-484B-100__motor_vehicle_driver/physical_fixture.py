"""CPU diagnostic outcomes for source-bound officer indication and response."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from officer_response import measure

HERE = Path(__file__).resolve().parent


def run(case_id: str, kind: str) -> dict:
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next((item for item in manifest["cases"] if item["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("unknown exact officer case")
    slug = case_id.rsplit("__", 1)[-1]
    diagnostic = json.loads((HERE / f"diagnostic-{slug}.json").read_text())
    files = diagnostic["files"]
    names = ("officer_context.json", "officer_direction.json", "subject_motion.json",
             "subject_motion_history.jsonl")
    hashes = {name: hashlib.sha256(files[name].encode()).hexdigest() for name in names}
    direction_data = json.loads(files["officer_direction.json"])
    command = direction_data["command"]
    expected = ("stopped_after_indication" if command == "stop" else "moved_after_indication")
    if "does_not_respond" in slug:
        expected = "no_observed_stop" if command == "stop" else "no_observed_movement"
    with TemporaryDirectory(prefix="officer-physical-") as temp:
        base = Path(temp)
        paths = {name: base / name for name in names[:3]}
        for name, path in paths.items():
            path.write_text(files[name])
        def observe():
            return measure(paths["officer_context.json"], paths["officer_direction.json"],
                           paths["subject_motion.json"], expected_actor="motor_vehicle_driver",
                           expected_command=command)
        observed = observe()
        if observed["observed_response"] != expected:
            raise ValueError("complete diagnostic response differs from the exact case")
        if kind == "complete_motion":
            status = "met"
        elif kind == "incomplete_motion":
            motion = json.loads(paths["subject_motion.json"].read_text())
            frame = direction_data["frame"]
            motion["frames"] = [row for row in motion["frames"] if row["frame"] <= frame + 1]
            paths["subject_motion.json"].write_text(json.dumps(motion))
            try:
                observe()
            except ValueError as error:
                if "at least two post-indication motion samples required" not in str(error):
                    raise
            else:
                raise ValueError("incomplete response span was accepted")
            status = "not_met"
        elif kind == "missing_evidence":
            paths["officer_direction.json"].unlink()
            try:
                observe()
            except ValueError as error:
                if "missing required source" not in str(error):
                    raise
            else:
                raise ValueError("missing indication source was accepted")
            status = "unverified"
        else:
            raise ValueError("unknown fixture kind")
    return {"case_id": case_id, "fixture_kind": kind, "fixture_only": True,
            "diagnostic_fixture": True, "actual_native_capture": False,
            "provenance_kind": "synthetic_fixture",
            "provenance_note": "Synthetic diagnostic source protocol; officer authority and legality need review",
            "physical_checks": {"maneuver": {
                "status": status,
                "method": "timed officer direction and joined original subject speed; perturbed response spans",
                "sources": {"source_sha256": hashes, "perturbation": kind},
                "missing_evidence": ["officer_direction.json"] if kind == "missing_evidence" else []}},
            "maneuver_completed": status == "met",
            "realized_observables": ({"observed_response": observed["observed_response"],
                                      "post_indication_samples": observed["post_indication_samples"]}
                                     if status == "met" else {}),
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "status": result["physical_checks"]["maneuver"]["status"],
                      "diagnostic_fixture": True}))
