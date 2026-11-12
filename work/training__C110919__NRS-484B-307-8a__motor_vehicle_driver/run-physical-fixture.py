"""Replay one CPU mock outcome or lifecycle branch for one right-turn case."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from physical_outcome import EVENTS, check_lifecycle, classify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=("reference", "contrast"))
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE / "update017-selected-pair-probe-manifest.json").read_text())
    entry = next(x for x in manifest["cases"] if x["case_id"].endswith("__" + args.case))
    if args.kind == "lifecycle":
        result = check_lifecycle(EVENTS, 0)
        for events, code in ((EVENTS[-1:] + EVENTS[:-1], 0), (EVENTS, 1)):
            try:
                check_lifecycle(events, code)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid lifecycle accepted")
        result.update({"cpu_fixture_mock": True, "original_owner_release_verified": False,
                       "construction_sha256": entry["construction_sha256"]})
    else:
        attempt = ROOT / ".runtime-work/c110919-update017-selected-pair-probe" / args.case / "primary/compatibility"
        raw = attempt / "native_samples.jsonl"
        road = attempt / "road_geometry.json"
        rows = [json.loads(line) for line in raw.read_text().splitlines()]
        geometry = json.loads(road.read_text())
        if len(rows) != 480 or not all(r.get("synthetic_diagnostic") is True and
                                        r.get("speed_provenance") == "synthetic_native_sample" for r in rows):
            raise ValueError("Diagnostic source provenance missing")
        if geometry.get("synthetic_diagnostic") is not True:
            raise ValueError("Diagnostic geometry provenance missing")
        source_hashes = {"native_samples.jsonl": sha(raw), "road_geometry.json": sha(road)}
        selected = copy.deepcopy(rows)
        for row in selected:
            row.pop("synthetic_diagnostic")
            row.pop("speed_provenance")
        geometry.pop("synthetic_diagnostic")
        if args.kind == "missing_evidence":
            selected.pop()
        elif args.kind == "incomplete_motion":
            selected[-1]["native_center_xy_m"] = [8.0, -7.0]
        result = classify(selected, geometry, provenance_kind="native", diagnostic_fixture=False)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise AssertionError("Physical branch differs")
        if classify(rows, geometry, provenance_kind="native", diagnostic_fixture=False)[
                "physical_checks"]["maneuver"]["status"] != "unverified":
            raise AssertionError("Synthetic source spoof accepted")
        result.update({"cpu_fixture_mock": True, "mock_input_provenance": "synthetic_native_sample",
                       "original_native_motion_verified": False,
                       "construction_sha256": entry["construction_sha256"],
                       "retained_source_sha256": source_hashes})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": entry["case_id"], "kind": args.kind,
                      "status": result.get("physical_checks", {}).get("maneuver", {}).get("status"),
                      "cpu_fixture_mock": True, "original_native_motion_verified": False}))


if __name__ == "__main__":
    main()
