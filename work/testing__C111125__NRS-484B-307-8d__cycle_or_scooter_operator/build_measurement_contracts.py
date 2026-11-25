"""Bind six exact bicycle red-signal requirements to source-only measurements."""
from __future__ import annotations

import json
from pathlib import Path

from analysis import ROWS, SOURCE_NAMES


HERE = Path(__file__).resolve().parent


def build():
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    dispositions = plan["requirement_dispositions"]
    if len(dispositions) != len(ROWS):
        raise ValueError("Exact bicycle measurement inventory changed")
    output = HERE / "contracts"
    output.mkdir(exist_ok=True)
    for case in plan["cases"]:
        requirements = []
        for index, ((key, method), disposition) in enumerate(zip(ROWS, dispositions)):
            if disposition["disposition_index"] != index or case["case_id"] not in disposition["case_ids"]:
                raise ValueError("Selected bicycle requirement identity changed")
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "output_key": key, "method": method.__name__,
                                 "inputs": list(SOURCE_NAMES), "kind": "measured", "value_type": "object"})
        contract = {"format": "worker-measurement-contract", "case_id": case["case_id"],
                    "requirements": requirements,
                    "negative": {"remove": ["source/detector.json"],
                                 "error_contains": "Missing required source: source/detector.json"},
                    "unresolved_judgments": ["official device and detector causal authority",
                                             "pedestrian and traffic right-of-way status",
                                             "bicycle rider and physical camera visibility",
                                             "legal outcome"]}
        suffix = case["case_id"].removeprefix(HERE.name + "__")
        (output / (suffix + ".json")).write_text(json.dumps(contract, indent=2) + "\n",
                                                      encoding="utf-8")
    print(str(len(plan["cases"])) + " exact source-bound bicycle measurement contracts")


if __name__ == "__main__":
    build()
