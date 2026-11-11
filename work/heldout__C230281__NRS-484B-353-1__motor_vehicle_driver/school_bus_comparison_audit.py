"""Independent comparison audit for school-bus stop and exceptions."""
import json
from pathlib import Path

def audit(paths,variable):
    if variable not in ("response","direction","divided_other_roadway","officer_control","red_cessation_restart") or len(paths)!=2:
        raise ValueError("two exact cases and a known comparison variable required")
    a,b=[json.loads(Path(p).read_text()) for p in paths]
    for r in (a,b):
        if len(r.get("source_refs",[]))!=3 or r.get("legal_conclusion") is not None:
            raise ValueError("source-bound observation missing or legal conclusion asserted")
    for key in ("subject_id","bus_id","red_on_frame","red_off_frame"):
        if a.get(key)!=b.get(key):raise ValueError("fixed bus/subject/signal changed: "+key)
    varies={"response":{"observed_stop_during_red","observed_pass_before_red_ceased"},
            "direction":{"approach_direction"},"divided_other_roadway":{"divided_highway","other_roadway"},
            "officer_control":{"traffic_officer_controlled"},
            "red_cessation_restart":{"observed_motion_after_red_ceased"}}[variable]
    keys=("approach_direction","divided_highway","other_roadway","traffic_officer_controlled",
          "observed_stop_during_red","observed_pass_before_red_ceased","observed_motion_after_red_ceased")
    for key in keys:
        if key not in varies and a.get(key)!=b.get(key):raise ValueError("held condition changed: "+key)
    if not any(a.get(key)!=b.get(key) for key in varies):raise ValueError("deliberate comparison variable did not change")
    return {"comparison_complete":True,"variable":variable,"fixed_conditions_checked":[k for k in keys if k not in varies],"legal_conclusion":None}
