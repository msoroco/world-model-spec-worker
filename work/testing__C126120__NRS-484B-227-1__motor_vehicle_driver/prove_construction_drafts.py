"""Check source-exact seven-case bundles and pinned measurement contracts."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
output_root=Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT","")).resolve()
if not output_root.is_relative_to(REPO/".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0,str(REPO/"runtime/scenario_pipeline"))

from worker_exchange.measurement_contract import validate as validate_measurements


def main():
    plan=json.loads((HERE/"case-plan.json").read_text())
    checked=[]
    for item in plan["cases"]:
        case_id=item["case_id"]
        suffix=case_id.rsplit("__",1)[-1]
        location=HERE/"cases"/suffix
        construction=json.loads((location/"construction.json").read_text())
        contract=json.loads((location/"measurement-contract.json").read_text())
        if construction["case_id"]!=case_id or construction["entrypoint"]!="runner.py":
            raise ValueError("exact construction identity differs: "+case_id)
        paths=set()
        for entry in construction["files"]:
            if entry.get("source"):
                source=REPO/entry["source"]
                if not source.is_relative_to(HERE) or source.read_text()!=entry["content"]:
                    raise ValueError("source-exact construction file changed: "+entry["path"])
            if entry["path"] in paths:
                raise ValueError("duplicate construction target: "+entry["path"])
            paths.add(entry["path"])
        for required in ("runner.py","analysis.py","scene.json","config.json",
                         "road.xodr","reviewed-median-context.json",
                         "authority-review-source.json"):
            if required not in paths:
                raise ValueError("construction lacks exact source: "+required)
        analysis=next(entry["content"] for entry in construction["files"]
                      if entry["path"]=="analysis.py")
        validate_measurements(contract,plan["requirement_dispositions"],analysis,case_id)
        checked.append(case_id)
    print(json.dumps({"source_exact_constructions":len(checked),
                      "pinned_measurement_contracts_valid":len(checked),
                      "delivery_ready_claimed":False}))


if __name__=="__main__":main()
