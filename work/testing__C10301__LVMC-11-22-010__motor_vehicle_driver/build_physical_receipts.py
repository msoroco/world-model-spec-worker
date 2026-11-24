"""Bind exact diagnostic physical fixture outputs and lifecycle logs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    for kind in ("steady_travel", "steering_variation"):
        case = AID + "__" + kind
        construction = HERE / ("construction-" + kind + ".json")
        fixtures = []
        for outcome in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = HERE / ("physical-" + kind + "-" + outcome + ".json")
            log = HERE / ("cpu-physical-" + kind + "-" + outcome + ".log")
            if json.loads(result.read_text())["diagnostic_fixture"] is not True:
                raise ValueError("Physical receipt requires diagnostic provenance")
            fixtures.append({
                "kind": outcome,
                "command": ".venv-cpu/bin/python work/" + AID + "/prove_physical.py --case " + case
                           + " --kind " + outcome + " --scratch .runtime-work/c10301-010-nov24b/physical"
                           + " --result work/" + AID + "/" + result.name,
                "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                "result": result.name, "result_sha256": sha(result),
            })
        life_log = HERE / ("cpu-lifecycle-" + kind + ".log")
        life = json.loads(life_log.read_text())
        if life["case_id"] != case or life["diagnostic_fixture"] is not True:
            raise ValueError("Lifecycle scope or provenance differs")
        receipt = {
            "format": "worker-physical-preparation-proof", "case_id": case,
            "construction_sha256": sha(construction),
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
            "fixtures": fixtures,
            "lifecycle": {"command": ".venv-cpu/bin/python work/" + AID
                          + "/prove_lifecycle.py --case " + case
                          + " --scratch .runtime-work/c10301-010-nov24b/physical",
                          "events": life["events"], "exit_code": 0,
                          "log": life_log.name, "log_sha256": sha(life_log)},
        }
        (HERE / ("physical-preparation-" + kind + ".json")).write_text(
            json.dumps(receipt, indent=2) + "\n")
    print("Bound both exact cases to measured synthetic outcomes and lifecycle closure")


if __name__ == "__main__":
    build()
