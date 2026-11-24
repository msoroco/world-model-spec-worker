"""Replay exact planned comparisons from sealed original Native traces."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_measure import audit_source_pair


VARIABLES = {
    "door_sweep_clearance": "body_gap_m",
    "door_side": "act_side",
    "selected_act": "observed_act",
}


def compare(plan_path: Path, spec_path: Path) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    comparison_id = spec.get("comparison_id")
    if comparison_id not in VARIABLES:
        raise ValueError("unknown exact comparison ID")
    rows = [row for row in plan.get("comparisons", [])
            if row.get("comparison_id") == comparison_id]
    if len(rows) != 1:
        raise ValueError("exact comparison is absent or duplicated in plan")
    expected_cases = rows[0]["case_ids"]
    sources = spec.get("sources")
    if not isinstance(sources, list) or [row.get("case_id") for row in sources] != expected_cases:
        raise ValueError("source cases differ from the exact planned comparison")
    if len(sources) < 2:
        raise ValueError("comparison requires at least two sealed sources")
    results = []
    for source in sources[1:]:
        first = sources[0]
        results.append(audit_source_pair(
            Path(first["path"]), first["sha256"], first["case_id"],
            first["act"], first["side"], Path(source["path"]),
            source["sha256"], source["case_id"], source["act"],
            source["side"], VARIABLES[comparison_id]))
    return {"comparison_id": comparison_id, "case_ids": expected_cases,
            "pair_audits": results, "legal_interference": "unresolved_judgment"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=Path(__file__).with_name("case-plan.json"))
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.plan, args.spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
