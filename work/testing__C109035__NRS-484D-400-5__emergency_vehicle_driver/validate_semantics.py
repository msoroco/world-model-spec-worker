"""Run the pinned semantic stage validators on the local source-bound draft."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "runtime" / "python"))
from scenario_pipeline.batch_pipeline.stages import validate


def main():
    folder = HERE / "proposals"
    get = lambda name: json.loads((folder / (name + ".json")).read_text())
    template, binding, cases = get("template"), get("bindings"), get("cases")
    judgments = [get("judgment-" + str(i)) for i in range(1, 5)]
    request = {"cell": {"cell_id": "C109035"}, "actor": "emergency_vehicle_driver",
               "law_id": "NRS-484D-400-5", "template_ids": [template["template_id"]]}
    law = {"text": template["quote"]}
    validate("relevance", get("relevance"), {"request": request,
             "law_records": {request["law_id"]: law}})
    validate("template", template, {"request": request, "law_record": law,
             "canonical_parameter_rules": {}})
    for row in judgments:
        validate("judgment_observables", row,
                 {"request": {"template_id": template["template_id"],
                              "phrase": row["phrase"], "note": row["note"]}})
    template["structure"]["judgment_calls_needed"] = [
        {**item, "observable_requirements": row["observable_requirements"]}
        for item, row in zip(template["structure"]["judgment_calls_needed"], judgments)]
    validate("bindings", binding, {"request": request, "canonical_parameter_rules": {}})
    validate("cases", cases, {"request": request, "dependencies": [binding],
             "templates": [template]})
    print("pinned semantic relevance/template/4 judgments/bindings/cases accepted")


if __name__ == "__main__":
    main()
