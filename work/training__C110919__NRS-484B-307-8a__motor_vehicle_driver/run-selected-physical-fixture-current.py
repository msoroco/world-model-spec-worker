"""Execute C110919 CPU physical branches on a current retained attempt."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from selected_physical_outcome import EVENTS, check_lifecycle, classify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

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
    entry = next(x for x in manifest["cases"] if x["case_id"] == args.case)
    if args.kind == "lifecycle":
        result = check_lifecycle(EVENTS, 0)
        for events, code in ((EVENTS[-1:] + EVENTS[:-1], 0), (EVENTS, 1)):
            try:
                check_lifecycle(events, code)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid lifecycle accepted")
        result.update(cpu_fixture_mock=True, original_owner_release_verified=False)
    else:
        source = args.attempt
        raw, road = source / "native_samples.jsonl", source / "road_geometry.json"
        rows = [json.loads(x) for x in raw.read_text().splitlines()]
        geometry = json.loads(road.read_text())
        if len(rows) != 480 or not all(x.get("synthetic_diagnostic") is True and
            x.get("speed_provenance") == "synthetic_native_sample" for x in rows):
            raise ValueError("Synthetic source provenance missing")
        if geometry.get("synthetic_diagnostic") is not True:
            raise ValueError("Synthetic road provenance missing")
        selected = copy.deepcopy(rows)
        for row in selected:
            row.pop("synthetic_diagnostic", None)
            row.pop("speed_provenance", None)
        geometry.pop("synthetic_diagnostic")
        if args.kind == "incomplete_motion":
            selected[-1]["native_center_xy_m"] = selected[0]["native_center_xy_m"]
            selected[-1]["native_body_xy_m"] = selected[0]["native_body_xy_m"]
        elif args.kind == "missing_evidence":
            selected.pop()
        result = classify(selected, geometry, provenance_kind="synthetic_fixture",
                          diagnostic_fixture=True)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise AssertionError("Mock branch differs: " + args.case + " " + args.kind)
        if classify(rows, geometry, provenance_kind="native", diagnostic_fixture=False)[
            "physical_checks"]["maneuver"]["status"] != "unverified":
            raise AssertionError("Synthetic source spoof accepted")
        result.update(cpu_fixture_mock=True, mock_input_provenance="synthetic_native_sample",
                      original_native_motion_verified=False,
                      retained_source_sha256={"native_samples.jsonl": sha(raw),
                                              "road_geometry.json": sha(road)})
    result["construction_sha256"] = entry["construction_sha256"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "status": result.get("physical_checks", {}).get("maneuver", {}).get("status"),
                      "cpu_fixture_mock": True, "original_native_motion_verified": False}))

if __name__ == "__main__":
    main()
