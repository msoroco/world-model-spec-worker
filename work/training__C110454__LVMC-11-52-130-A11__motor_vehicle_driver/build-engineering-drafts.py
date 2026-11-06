"""Eight distinct source-pinned but unproven parking-law construction drafts."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("engineering",HERE/"native/engineering.py")
engineering=importlib.util.module_from_spec(spec);spec.loader.exec_module(engineering)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source=HERE/"../../inputs"/HERE.name/"assignment.json"
    road=HERE/"native/road.xodr"
    plans=[]
    for case in engineering.CASES:
        route=HERE/"native/routes"/(case+".json")
        for candidate in engineering.CANDIDATES:
            plan=engineering.plan(case,candidate)|{
                "case_id":HERE.name+"__"+case,"law_id":"LVMC-11-52-130-A11",
                "cell_id":"C110454","actor":"motor_vehicle_driver",
                "comparison_variable":"parked_footprint_distance_to_intersection",
                "source_assignment_sha256":sha(source),"road_sha256":sha(road),
                "route_sha256":sha(route),"status":"unselected_draft",
                "exact_offline_receipt":None,"compatibility_receipt":None}
            plan["construction_sha256"]=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
            plans.append(plan)
    if len({p["construction_sha256"] for p in plans})!=8:raise ValueError("Construction hash collision")
    (HERE/"engineering-drafts.json").write_text(json.dumps({"format":"unselected-lvmc-parking-drafts-v1",
                                                    "plans":plans},indent=2)+"\n")
    print(json.dumps({"plans":8,"distinct_sha256":8,"selected":0,"exact_offline_proven":0}))


if __name__=="__main__":main()
