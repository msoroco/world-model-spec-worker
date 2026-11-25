"""Bind seven exact selected requirements to the saved-only finalizer."""
from __future__ import annotations

import json
from pathlib import Path

from analysis import ROWS

HERE = Path(__file__).resolve().parent
INPUTS = ["native-site.json", "saved-manifest.json", "original-events.json",
          "video_frames.jsonl", "trace.jsonl", "media-receipt.json"]


def build():
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    dispositions = plan["requirement_dispositions"]
    if len(dispositions) != len(ROWS):
        raise ValueError("Exact measurement inventory changed")
    output = HERE / "contracts"
    output.mkdir(exist_ok=True)
    for case in plan["cases"]:
        requirements = []
        for index, ((key, method), disposition) in enumerate(zip(ROWS, dispositions)):
            if disposition["disposition_index"] != index or case["case_id"] not in disposition["case_ids"]:
                raise ValueError("Selected disposition identity changed")
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "output_key": key, "method": method.__name__,
                                 "inputs": INPUTS, "kind": "measured", "value_type": "object"})
        contract = {"format": "worker-measurement-contract", "case_id": case["case_id"],
                    "requirements": requirements,
                    "negative": {"remove": ["native-site.json"],
                                 "error_contains": "Missing required source: native-site.json"},
                    "unresolved_judgments": ["participant lawful status",
                                             "device causality review", "physical pixel visibility",
                                             "legal outcome"]}
        suffix = case["case_id"].rsplit("__", 1)[-1]
        (output / (suffix + ".json")).write_text(json.dumps(contract, indent=2) + "\n",
                                                      encoding="utf-8")
    print("seven exact saved-only measurement contracts")


if __name__ == "__main__":
    build()
