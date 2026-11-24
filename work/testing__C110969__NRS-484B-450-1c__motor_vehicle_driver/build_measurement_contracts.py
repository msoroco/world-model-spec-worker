"""Bind each selected frozen witness requirement to saved original packets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METHOD = {
    0: ("intersection_contact", "measure_intersection_contact", ["boundary.json", "trace.json"]),
    1: ("stop_activity", "measure_activity", ["activity.json", "trace.json"]),
    2: ("stand_activity", "measure_activity", ["activity.json", "trace.json"]),
    3: ("park_activity", "measure_activity", ["activity.json", "trace.json"]),
    4: ("traffic_conflict", "measure_traffic_conflict", ["activity.json"]),
    5: ("law_direction", "measure_law_direction", ["activity.json"]),
    6: ("officer_direction", "measure_officer_direction", ["activity.json"]),
    7: ("device_direction", "measure_device_direction", ["activity.json"]),
}


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = plan["requirement_dispositions"]
    from worker_exchange.measurement_contract import validate
    analysis_code = (ROOT / "analysis.py").read_text()
    for case in plan["cases"]:
        ident = case["case_id"]
        suffix = ident.removeprefix(ROOT.name + "__")
        selected = []
        for i, disposition in enumerate(rows):
            if disposition["status"] != "selected_required" or ident not in disposition["case_ids"]:
                continue
            key, method, inputs = METHOD[i]
            selected.append({"disposition_index": i, "requirement": disposition["requirement"],
                             "source": disposition["source"], "output_key": key,
                             "method": method, "value_type": "object", "kind": "measured", "inputs": inputs})
        if not selected:
            continue
        removed = selected[0]["inputs"][0]
        spec = {"format": "worker-measurement-contract", "assignment_id": ROOT.name,
                "case_id": ident, "requirements": selected,
                "negative": {"remove": [removed], "error_contains": "Missing required source: " + removed},
                "scope": "source-bound saved observation; physical and statutory judgments unresolved"}
        validate(spec, rows, analysis_code, ident)
        folder = ROOT / "cases" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "measurement-contract.json").write_text(json.dumps(spec, sort_keys=True, indent=2) + "\n")
    print("validated nine selected measurement contracts")


if __name__ == "__main__":
    build()
