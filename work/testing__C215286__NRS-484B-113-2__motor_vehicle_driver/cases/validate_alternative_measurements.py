"""Validate staged intersection and corner contracts against the pinned runtime."""

import json
from pathlib import Path

from worker_exchange.measurement_contract import validate


ROOT = Path(__file__).resolve().parents[1]


def main():
    plan = json.loads((ROOT / "cases/alternative-measurement-plan.json").read_text())
    code = (ROOT / "reverse_alternative_finalizer.py").read_text()
    names = (
        "reverse_into_intersection",
        "reverse_stops_before_intersection",
        "reverse_around_street_corner",
        "reverse_stops_before_street_corner",
    )
    for name in names:
        contract = json.loads((ROOT / "cases" / (name + "-measurement-contract.json")).read_text())
        case_id = ROOT.name + "__" + name
        rows = validate(contract, plan["requirement_dispositions"], code, case_id)
        if len(rows) != 1 or len(rows[0]["inputs"]) < 6:
            raise ValueError("Alternative contract lacks original site and motion sources: " + name)
        print(name, "contract passed", len(rows[0]["inputs"]), "bound sources")


if __name__ == "__main__":
    main()
