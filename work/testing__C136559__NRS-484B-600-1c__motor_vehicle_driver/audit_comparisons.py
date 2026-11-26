"""Production source-bound six-comparison dispatcher for retained originals."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_speed import audit_pair
from speed_source_review import ASSIGNMENT


ROOT = Path(__file__).resolve().parent


def audit(roots: dict) -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    expected = {case["case_id"] for case in plan["cases"]}
    if set(roots) != expected:
        raise ValueError("all eight exact original attempts required for six comparisons")
    inventories = {}
    for case, name in roots.items():
        root = Path(name).resolve()
        if not root.is_dir() or not (root / "inventory.json").is_file():
            raise ValueError("original comparison inventory missing: " + case)
        inventories[case] = (root, json.loads((root / "inventory.json").read_text()))
    base_case = ASSIGNMENT + "__above"
    base_root, base_inventory = inventories[base_case]
    reports = []
    expected_alternatives = {
        "strict_rate_boundary": ("below", "equal"),
        "governed_portion": ("outside_zone",),
        "governed_direction": ("opposite_direction",),
        "authority": ("non_authority_sign",),
        "units": ("metric_equivalent",),
        "source_visibility": ("sign_not_in_view",),
    }
    if {row["comparison_id"] for row in plan["comparisons"]} != set(expected_alternatives):
        raise ValueError("six frozen comparison identities changed")
    for comparison in plan["comparisons"]:
        name = comparison["comparison_id"]
        members = {ASSIGNMENT + "__" + suffix for suffix in expected_alternatives[name]} | {base_case}
        if set(comparison["case_ids"]) != members:
            raise ValueError("frozen comparison members changed: " + name)
        pairs = []
        for suffix in expected_alternatives[name]:
            other_root, other_inventory = inventories[ASSIGNMENT + "__" + suffix]
            pairs.append(audit_pair(base_root, base_inventory, other_root, other_inventory, suffix))
        reports.append({"comparison_id": name, "case_ids": sorted(members),
                        "fixed_conditions": comparison["fixed_conditions"],
                        "deliberate_differences": comparison["deliberate_differences"],
                        "pair_audits": pairs})
    return {"format": "c136559-original-six-comparison-audit-v1",
            "assignment_id": ASSIGNMENT, "comparisons": reports,
            "physical_completion_confirmed": False,
            "legal_applicability": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite original comparison audit")
    result = audit(json.loads(args.attempt_map.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
