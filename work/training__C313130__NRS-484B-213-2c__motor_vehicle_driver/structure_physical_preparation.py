"""Synthetic structure motion and lifecycle tests; no Native acceptance claim."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(source, context, case, kind, output):
    source, context, output = Path(source), Path(context), Path(output)
    rows = [json.loads(line) for line in source.read_text().splitlines()] if source.is_file() else []
    structure_start = json.loads(context.read_text()).get("approach_structure_x_m") if context.is_file() else None
    valid = [(row.get("native_frame"), row.get("time_s"),
              min(point[0] for point in row["body_xy_m"]),
              max(point[0] for point in row["body_xy_m"]))
             for row in rows if isinstance(row.get("body_xy_m"), list) and
             len(row["body_xy_m"]) == 4]
    complete = (len(valid) == 600 and structure_start is not None and
                [r[0] for r in valid] == list(range(600)) and
                all(abs(r[1] - i / 20) < 1e-6 for i, r in enumerate(valid)) and
                valid[0][3] < structure_start - 30.48 and valid[-1][2] > structure_start and
                all(a[2] <= b[2] for a, b in zip(valid, valid[1:])))
    status = "unverified" if not source.is_file() or not context.is_file() else (
        "met" if complete else "not_met")
    if kind == "incomplete_motion" and status != "not_met":
        raise ValueError("Incomplete structure fixture unexpectedly completed")
    if kind == "missing_evidence" and status != "unverified":
        raise ValueError("Missing structure fixture unexpectedly measured")
    if kind == "complete_motion" and status != "met":
        raise ValueError("Complete structure fixture did not approach/traverse structure start")
    sources = {path.name: sha(path) for path in (source, context) if path.is_file()}
    if not sources:
        sources = {"missing": source.name}
    check = {"status": status,
        "method": "Joined 600 synthetic full-body footprints approach and traverse the authored structure start at 20 Hz",
        "sources": sources, "observed_frames": len(valid),
        "physical_structure_verified": False, "legal_view_obstructed": "unassessed"}
    result = {"case_id": case, "physical_checks": {"maneuver": check},
        "maneuver_completed": status == "met",
        "realized_observables": {"structure_start_traversed": True} if status == "met" else {},
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": case, "kind": kind, "status": status,
                      "observed_frames": len(valid)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    assess(args.source, args.context, args.case, args.kind, args.output)


if __name__ == "__main__":
    main()
