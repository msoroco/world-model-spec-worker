"""Run one source-shaped CPU branch fixture for a selected maneuver."""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from physical_outcome import check_lifecycle, classify


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion",
                                           "missing_evidence", "lifecycle"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=HERE / "execution-manifest.json")
    parser.add_argument("--run-root", type=Path,
                        default=ROOT / ".runtime-work/c110454-update025-six-selected")
    args = parser.parse_args()
    suffix = args.case.removeprefix(HERE.name + "__")
    if suffix == args.case:
        raise ValueError("Wrong selected assignment")
    manifest = json.loads(args.manifest.read_text())
    entry = next((row for row in manifest["cases"] if row["case_id"] == args.case), None)
    if entry is None:
        raise ValueError("Unselected case")
    if args.kind == "lifecycle":
        events = ["capture_finished", "encoders_closed", "restoration_verified",
                  "native_exit", "owner_released", "saved_processing_started"]
        outcome = check_lifecycle(events, native_exit_code=0)
        for bad, code in ((events[:-2] + events[-1:] + events[-2:-1], 0), (events, 1)):
            try:
                check_lifecycle(bad, native_exit_code=code)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid lifecycle accepted")
        outcome.update({"cpu_fixture_mock": True, "original_owner_release_verified": False,
                        "construction_sha256": entry["construction_sha256"]})
    else:
        attempt = args.run_root / suffix / "primary/compatibility"
        names = ("native_samples.jsonl", "road_geometry.json",
                 "context.json" if suffix.startswith("traversal_") or suffix in ("reference", "contrast") else "statutory_context.json")
        samples = [json.loads(line) for line in (attempt / names[0]).read_text().splitlines()]
        survey = json.loads((attempt / names[1]).read_text())
        context = json.loads((attempt / names[2]).read_text())
        if not all(row.get("synthetic_diagnostic") is True and
                   row.get("speed_provenance") == "synthetic_native_sample" for row in samples):
            raise ValueError("Expected retained diagnostic source provenance")
        source_hashes = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                         for name in names}
        if args.kind == "missing_evidence":
            selected = samples[:-1]
        else:
            selected = copy.deepcopy(samples)
            # Exercise the Native branch with an in-memory mock. Never rewrite
            # retained diagnostic sources or their synthetic speed labels.
            for row in selected:
                row.pop("synthetic_diagnostic", None)
                row.pop("speed_provenance", None)
            if args.kind == "incomplete_motion":
                selected[-1]["speed_m_s"] = 1.0
        outcome = classify(selected, survey, suffix, context,
                           provenance_kind="native", diagnostic_fixture=False)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if outcome["physical_checks"]["maneuver"]["status"] != expected:
            raise AssertionError("Physical fixture status differs")
        outcome.update({"cpu_fixture_mock": True, "mock_input_provenance": "synthetic_native_sample",
                        "original_native_motion_verified": False,
                        "construction_sha256": entry["construction_sha256"],
                        "retained_source_sha256": source_hashes})
    write(args.output, outcome)
    print(json.dumps({"case_id": args.case, "kind": args.kind, "result": str(args.output),
                      "cpu_fixture_mock": True, "original_native_motion_verified": False}))


if __name__ == "__main__":
    main()
