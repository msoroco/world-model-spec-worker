"""Independent source/disposition and synthetic receipt audit for witness contracts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
plan=json.loads((HERE/"case-plan.json").read_text())
disposition=plan["requirement_dispositions"][0]
fixture=ROOT/".runtime-work/c110454-lvmc-contract-fixtures"
results={}
for case,relation in (("witness_1","outside_15_ft"),("witness_2","within_15_ft")):
    path=HERE/"draft-measurement-contracts"/case/"measurement-contract.json"
    contract=json.loads(path.read_text())
    if contract["case_id"]!=HERE.name+"__"+case:
        raise ValueError("Contract case identity differs")
    if len(contract["requirements"])!=1:
        raise ValueError("Witness requirement binding differs")
    row=contract["requirements"][0]
    if (row["disposition_index"],row["requirement"],row["source"])!=(0,disposition["requirement"],disposition["source"]):
        raise ValueError("Exact statutory disposition binding differs")
    if row["method"]!="measure_case_sources" or row["inputs"]!=["native_parking_history.json"]:
        raise ValueError("Saved source method differs")
    source=fixture/case/"native_parking_history.json"
    packet=json.loads(source.read_text())
    if len(packet["frames"])!=480 or not packet.get("synthetic_fixture"):
        raise ValueError("Synthetic fixture identity differs")
    rest=[r for r in packet["frames"] if r["speed_m_s"]<=.05]
    if len(rest)!=80 or [r["native_frame"] for r in rest]!=list(range(400,480)):
        raise ValueError("Continuous stop interval differs")
    distance=min(min(p[0] for p in r["body_xy_m"])-packet["intersection_entry_boundary_x_m"] for r in rest)
    observed="within_15_ft" if distance<4.572 else "outside_15_ft"
    if observed!=relation:raise ValueError("Measured witness relation differs")
    if contract["negative"]["remove"]!=["native_parking_history.json"]:
        raise ValueError("Case-specific negative differs")
    results[case]={"distance_m":distance,"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
                   "contract_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
print(json.dumps({"passed":True,"synthetic_only":True,"witnesses":results,
                  "selected_delivery_audit":False},sort_keys=True))
