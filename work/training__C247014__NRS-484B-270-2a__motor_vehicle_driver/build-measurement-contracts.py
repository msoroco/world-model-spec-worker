"""Bind each selected pass case to its source-joined saved measurement."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCES = ["participant-poses.jsonl", "trace.jsonl", "video_frames.jsonl",
           "road.xodr", "pass-context.json", "capture/evidence.jsonl"]


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    dispositions = plan["requirement_dispositions"]
    if len(dispositions) != 2 or len(plan["cases"]) != 4:
        raise ValueError("Four-case selected source plan differs")
    for index, disposition in enumerate(dispositions):
        if not disposition.get("case_ids") or disposition["source"] != "NRS 484B.270(2)(a)":
            raise ValueError("Exact statutory source or case binding differs")
        disposition["status"] = "selected_required"
        disposition["evidence_or_gap"] = (
            "Exact original Native lane and actor readback, public compatibility, saved processing, "
            "physical and independent audits pending; no due-care or safety judgment")
        disposition["disposition_index"] = index
    for case in plan["cases"]:
        case["kind"] = "delivery"
        case["delivery_readiness"] = "selected_cpu_draft_incomplete"
        suffix = case["case_id"].rsplit("__", 1)[-1]
        applicable = [(i, row) for i, row in enumerate(dispositions)
                      if case["case_id"] in row["case_ids"]]
        if len(applicable) != 1:
            raise ValueError("Each case needs one exact selected disposition")
        i, row = applicable[0]
        contract = {"format": "worker-measurement-contract", "case_id": case["case_id"],
                    "requirements": [{"disposition_index": i,
                                      "requirement": row["requirement"], "source": row["source"],
                                      "output_key": "cycle_pass", "method": "derive",
                                      "kind": "measured", "value_type": "object",
                                      "inputs": SOURCES}],
                    "negative": {"remove": ["pass-context.json"],
                                 "error_contains": "Missing required source: pass-context.json"}}
        (HERE / (suffix + "-measurement-contract.json")).write_text(
            json.dumps(contract, indent=2) + "\n")
    (HERE / "case-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"selected_dispositions": 2, "case_measurement_contracts": 4}))


if __name__ == "__main__":
    main()
