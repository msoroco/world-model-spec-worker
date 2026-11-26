"""Source-derived CPU triad for the selected left-turn physical criterion.

All inputs are synthetic diagnostics. No result here is an original Native run.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion",
                                           "missing_evidence"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "").endswith("c329654-output"):
        raise ValueError("Set the assignment scratch output root before runtime import")
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / "runtime"))
    from scenario_pipeline.worker_exchange.native_output import assess_physical

    source = Path(args.source).resolve()
    scratch = repo / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c329654-physical-") as name:
        root = Path(name)
        for rel in ("config.json", "video_frames.jsonl", "trace.jsonl",
                    "interaction_history.jsonl", "road_geometry.json"):
            shutil.copy2(source / rel, root / rel)
        if args.kind == "missing_evidence":
            (root / "interaction_history.jsonl").unlink()
        elif args.kind == "incomplete_motion":
            rows = [json.loads(line) for line in
                    (root / "interaction_history.jsonl").read_text().splitlines()]
            for row in rows:
                for point in row["subject_body_vertices_m"]:
                    point[1] = min(point[1], 5.0)
            (root / "interaction_history.jsonl").write_text(
                "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
        config = json.loads((root / "config.json").read_text())
        assessment = assess_physical(root, config)
        maneuver = assessment["physical_checks"]["maneuver"]
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if maneuver["status"] != expected:
            raise AssertionError((args.kind, maneuver["status"], expected))
        motion = assessment["realized_observables"].get("original_motion", {})
        realized = ({"sampled_path_m": motion["sampled_path_m"],
                     "displacement_m": motion["displacement_m"]} if motion else {})
        result = {"format": "c329654-synthetic-physical-triad-v1",
                  "case_id": config["case_id"], "fixture_kind": args.kind,
                  "physical_checks": assessment["physical_checks"],
                  "maneuver_completed": assessment["maneuver_completed"],
                  "realized_observables": realized,
                  "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                  "physical_acceptance_claimed": False,
                  "legal_priority_verdict": None}
        Path(args.output).write_text(json.dumps(result, separators=(",", ":")) + "\n")
        print(json.dumps({"case_id": config["case_id"], "fixture_kind": args.kind,
                          "maneuver_status": maneuver["status"],
                          "source_count": len(maneuver["sources"])}))


if __name__ == "__main__":
    main()
