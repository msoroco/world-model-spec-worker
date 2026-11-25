"""Compare two sealed original stand attempts without deciding the law."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from stand import SourceError
from stand_source_sweep import extract


HERE = Path(__file__).resolve().parent
METRIC = {
    "access_mode": "access_obstructed_during_stop_frames",
    "loading_mode": "loading_during_stop_frames",
    "entrant_mode": "entrant_status_during_stop_frames",
}


def _sha(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise SourceError("original comparison source missing: " + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _observations(root, sweep):
    attempt = json.loads((root / "attempt-source.json").read_text(encoding="utf-8"))
    ref = attempt["actor_rows"]
    path = root / ref["path"]
    if not path.resolve().is_relative_to(root.resolve()) or _sha(path) != ref["sha256"]:
        raise SourceError("original comparison actor rows changed")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if len(rows) != 900 or len({row["frame"] for row in rows}) != 900:
        raise SourceError("original comparison actor history incomplete")
    stopped = [row for row in rows if row["subject_speed_mps"] < 0.1]
    measured = sweep["measurements"]
    if (len(stopped) != measured["stopped_frames"] or
            sum(row["passenger_loading_active"] for row in stopped) != measured["loading_during_stop_frames"] or
            sum(row["access_obstructed"] for row in stopped) != measured["access_obstructed_during_stop_frames"]):
        raise SourceError("original comparison measurements differ from source sweep")
    entrant = (sum(row["entrant_waiting"] for row in stopped),
               sum(row["entrant_about_to_enter"] for row in stopped))
    if sum(row["entrant_waiting"] or row["entrant_about_to_enter"] for row in stopped) != measured["entrant_waiting_or_about_during_stop_frames"]:
        raise SourceError("original comparison entrant history differs from source sweep")
    return {"access_obstructed_during_stop_frames": measured["access_obstructed_during_stop_frames"],
            "loading_during_stop_frames": measured["loading_during_stop_frames"],
            "entrant_status_during_stop_frames": entrant}


def _candidate(root, case_id, manifest):
    path = root / "candidate-selection.json"
    selection = json.loads(path.read_text(encoding="utf-8"))
    entry = next((item for item in manifest["cases"] if item["case_id"] == case_id), None)
    if entry is None:
        raise SourceError("comparison case absent from selected manifest")
    ident = selection.get("candidate_id")
    selected = entry if ident == "primary" else next(
        (item for item in entry["candidates"] if item["id"] == ident), None)
    if (selected is None or selection.get("format") != "worker-candidate-selection" or
            selection.get("case_id") != case_id or
            selection.get("construction_sha256") != selected["construction_sha256"] or
            selection.get("manifest_sha256") != _sha(HERE / "execution-manifest.json")):
        raise SourceError("original comparison candidate selection differs from manifest")
    return ident


def audit(comparison_id, left_root, right_root, site_sha256, vehicle_sha256):
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    comparison = next((item for item in plan["comparisons"]
                       if item["comparison_id"] == comparison_id), None)
    if comparison is None:
        raise SourceError("unknown exact comparison")
    cases = {item["case_id"]: item for item in plan["cases"]}
    left_root, right_root = Path(left_root).resolve(), Path(right_root).resolve()
    if left_root == right_root:
        raise SourceError("comparison needs two independent original attempts")
    roots = (left_root, right_root)
    sweeps = [extract(root, site_sha256, vehicle_sha256) for root in roots]
    if [sweep["case_id"] for sweep in sweeps] != comparison["case_ids"]:
        raise SourceError("original comparison exact case identities differ")
    manifest = json.loads((HERE / "execution-manifest.json").read_text(encoding="utf-8"))
    candidates = [_candidate(root, case_id, manifest)
                  for root, case_id in zip(roots, comparison["case_ids"])]
    if candidates[0] != candidates[1]:
        raise SourceError("comparison changed fixed stand spawn candidate")
    difference = comparison["deliberate_differences"]
    if len(difference) != 1 or difference[0] not in METRIC:
        raise SourceError("comparison has no single declared mode difference")
    fixed_modes = [mode for mode in METRIC if mode != difference[0]]
    left_case, right_case = [cases[case_id] for case_id in comparison["case_ids"]]
    if any(left_case[mode] != right_case[mode] for mode in fixed_modes):
        raise SourceError("comparison changed a fixed case mode")
    if left_case[difference[0]] == right_case[difference[0]]:
        raise SourceError("comparison omitted declared case mode difference")
    observations = [_observations(root, sweep) for root, sweep in zip(roots, sweeps)]
    metric = METRIC[difference[0]]
    if observations[0][metric] == observations[1][metric]:
        raise SourceError("declared original measured difference absent")
    return {
        "format": "c135087-original-comparison-audit-v1",
        "comparison_id": comparison_id,
        "case_ids": comparison["case_ids"],
        "attempt_source_sha256": [_sha(root / "attempt-source.json") for root in roots],
        "site_sha256": site_sha256,
        "vehicle_sha256": vehicle_sha256,
        "fixed_modes_checked": fixed_modes,
        "candidate_id": candidates[0],
        "deliberate_mode": difference[0],
        "measured_key": metric,
        "measured_values": [observation[metric] for observation in observations],
        "source_sweep_sha256": [hashlib.sha256(json.dumps(sweep, sort_keys=True).encode()).hexdigest()
                                for sweep in sweeps],
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left-attempt", required=True)
    parser.add_argument("--right-attempt", required=True)
    parser.add_argument("--reviewed-site-sha256", required=True)
    parser.add_argument("--reviewed-vehicle-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.left_attempt, args.right_attempt,
                   args.reviewed_site_sha256, args.reviewed_vehicle_sha256)
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
