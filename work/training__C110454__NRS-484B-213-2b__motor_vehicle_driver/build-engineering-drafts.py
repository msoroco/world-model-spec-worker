"""Materialize unselected, source-pinned C110454 construction drafts."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("engineering", HERE / "native/engineering.py")
engineering = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engineering)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assignment = HERE.name
    source = {name: sha(HERE / "../../inputs" / assignment / name)
              for name in ("assignment.json", "witnesses.json")}
    road = sha(HERE / "native/road.xodr")
    plans = []
    for case in engineering.CASES:
        route = sha(HERE / "native/routes" / (case + ".json"))
        for candidate in engineering.CANDIDATES:
            plan = engineering.parameters(case, candidate) | {
                "case_id": assignment + "__" + case,
                "cell_id": "C110454", "law_id": "NRS-484B-213-2b",
                "actor": "motor_vehicle_driver",
                "comparison_variable": "left_side_entry_distance_to_intersection",
                "map_sha256": road, "route_sha256": route,
                "frozen_source_sha256": source,
                "status": "unselected_draft",
                "offline_proof": None, "exact_compatibility_proof": None,
            }
            plan["construction_sha256"] = hashlib.sha256(
                json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            plans.append(plan)
    if len({p["construction_sha256"] for p in plans}) != 8:
        raise ValueError("Construction identity collision")
    (HERE / "engineering-drafts.json").write_text(json.dumps({
        "format": "unselected-c110454-construction-proposals-v1",
        "plans": plans, "physical_success_claimed": False}, indent=2) + "\n")
    print(json.dumps({"plans": len(plans), "distinct_sha256": 8,
                      "selected": 0, "offline_proven": 0, "compatibility_proven": 0}))


if __name__ == "__main__":
    main()
