"""Add the exact 15 mph CPU boundary source case without changing existing IDs."""

from __future__ import annotations

import json
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
PATH = WORK / "case-plan.json"


def main():
    plan = json.loads(PATH.read_text())
    base = next(case for case in plan["cases"] if case["case_id"].endswith("__condition_a"))
    case_id = base["case_id"].removesuffix("condition_a") + "condition_at"
    if case_id not in {case["case_id"] for case in plan["cases"]}:
        case = json.loads(json.dumps(base))
        case["case_id"] = case_id
        case["condition_index"] = len(plan["cases"])
        case["construction_design"]["speed_mode"] = "at_limit_traversal"
        case["claim"] = "Same sourced sight geometry; requested traversal at exactly 15 mph. No legal or physical outcome asserted."
        plan["cases"].insert(1, case)
        for disposition in plan["requirement_dispositions"]:
            disposition["case_ids"].append(case_id)
        comparison = json.loads(json.dumps(plan["comparisons"][0]))
        comparison["comparison_id"] = WORK.name + "__speed_at_15_mph"
        comparison["case_ids"] = [base["case_id"], case_id]
        comparison["deliberate_differences"] = ["traversal speed request and measured original speed at 15 mph"]
        plan["comparisons"].insert(1, comparison)
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 30,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "at-grade crossing, ego approach, both railway directions and two source rail vehicles", "interval": "entire 30 second original run"},
            {"view": "approach", "subject": "ego final 100 foot approach and crossing traversal", "interval": "approach through clearance"},
            {"view": "reference_corner", "subject": "signed left and right rail sight endpoints, crossing geometry and device", "interval": "last 100 feet of approach"},
            {"view": "driver_reference", "subject": "ego eye proxy, flagman duty and signal indication", "interval": "last 100 feet of approach through crossing clearance"},
        ],
    }
    PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print("planned cases", len(plan["cases"]), "comparisons", len(plan["comparisons"]))


if __name__ == "__main__":
    main()
