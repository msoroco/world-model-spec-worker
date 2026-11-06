"""Build and validate pinned witness contracts; leave selection unclaimed."""
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT/"runtime/pipeline"))
from scenario_pipeline.worker_exchange.measurement_contract import validate,verify_report

spec=importlib.util.spec_from_file_location("parking_analysis",HERE/"saved/analysis.py")
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)
plan=json.loads((HERE/"case-plan.json").read_text())
dispositions=plan["requirement_dispositions"]
out=HERE/"draft-measurement-contracts";out.mkdir(exist_ok=True)
synthetic=ROOT/".runtime-work/c110454-lvmc-synthetic"
fixtures=ROOT/".runtime-work/c110454-lvmc-contract-fixtures"
for case in ("witness_1","witness_2"):
    case_id=HERE.name+"__"+case
    contract={"format":"worker-measurement-contract-v1","case_id":case_id,
              "requirements":[{"disposition_index":0,"requirement":dispositions[0]["requirement"],
                               "source":dispositions[0]["source"],
                               "output_key":"parked_body_distance_and_rest_interval",
                               "method":"measure_case_sources","value_type":"object","kind":"measured",
                               "inputs":["native_parking_history.json"]}],
              "negative":{"remove":["native_parking_history.json"],
                          "error_contains":"Missing required source: native_parking_history.json"}}
    validate(contract,dispositions,(HERE/"saved/analysis.py").read_text(),case_id)
    contract_folder=out/case;contract_folder.mkdir(exist_ok=True)
    (contract_folder/"measurement-contract.json").write_text(json.dumps(contract,indent=2)+"\n")
    folder=fixtures/case;folder.mkdir(parents=True,exist_ok=True)
    source=synthetic/(case+"-native.json")
    (folder/"native_parking_history.json").write_bytes(source.read_bytes())
    item=analysis.measure_case_sources(folder)
    verify_report(contract,{"measurements":{"parked_body_distance_and_rest_interval":item}},folder)
    if item["value"]["sampled_relation"] != ("outside_15_ft" if case=="witness_1" else "within_15_ft"):
        raise ValueError("Controlled source relation differs")
    removed=folder/"native_parking_history.json"
    removed.rename(folder/"native_parking_history.removed")
    try:
        try:analysis.measure_case_sources(folder)
        except ValueError as error:
            if str(error)!=contract["negative"]["error_contains"]:raise
        else:raise ValueError("Contract negative passed")
    finally:
        (folder/"native_parking_history.removed").rename(removed)
print(json.dumps({"contracts":2,"pinned_validator_passed":True,
                  "synthetic_saved_positives":2,"removed_source_negatives":2,
                  "selected":0,"physical_observation":False}))
