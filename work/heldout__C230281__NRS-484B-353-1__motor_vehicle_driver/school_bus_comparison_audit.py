"""Independent comparison audit for school-bus stop and exceptions."""
import json
import math
from pathlib import Path

def audit(paths,variable):
    if variable not in ("response","direction","divided_other_roadway","officer_control","red_cessation_restart","premature_restart") or len(paths)!=2:
        raise ValueError("two exact cases and a known comparison variable required")
    a,b=[json.loads(Path(p).read_text()) for p in paths]
    for r in (a,b):
        if len(r.get("source_refs",[]))!=3 or r.get("legal_conclusion") is not None:
            raise ValueError("source-bound observation missing or legal conclusion asserted")
        hashes=r.get("source_sha256")
        if not isinstance(hashes,dict) or set(hashes)!={"context","signal","motion"} or any(
                not isinstance(v,str) or len(v)!=64 or any(c not in "0123456789abcdef" for c in v)
                for v in hashes.values()):
            raise ValueError("original source hashes missing")
        if r.get("observed_stop_during_red") != (r.get("first_stop_frame") is not None):
            raise ValueError("inconsistent original stop timing")
        if r.get("first_stop_frame") is None and r.get("stop_latency_s") is not None:
            raise ValueError("stop latency without a stop frame")
        if r.get("first_stop_frame") is not None:
            rate=r.get("motion_rate_hz")
            if type(rate) not in (int,float) or not math.isfinite(rate) or rate<=0 or r.get("stop_latency_s") != (r["first_stop_frame"]-r["red_on_frame"])/rate:
                raise ValueError("inconsistent original stop latency")
        if r.get("observed_pass_before_red_ceased") != (r.get("first_pass_frame") is not None and r["first_pass_frame"]<r["red_off_frame"]):
            raise ValueError("inconsistent original pass timing")
        if r.get("observed_held_until_red_ceased") != (r["observed_stop_during_red"] and not r.get("observed_early_restart_during_red") and not r["observed_pass_before_red_ceased"]):
            raise ValueError("inconsistent original hold interval")
    for key in ("subject_id","bus_id","red_on_frame","red_off_frame","motion_rate_hz"):
        if a.get(key)!=b.get(key):raise ValueError("fixed bus/subject/signal changed: "+key)
    if a["source_sha256"]["signal"] != b["source_sha256"]["signal"]:
        raise ValueError("fixed original signal source changed")
    if variable in ("response","red_cessation_restart","premature_restart") and a["source_sha256"]["context"] != b["source_sha256"]["context"]:
        raise ValueError("fixed original context source changed")
    varies={"response":{"observed_stop_during_red","observed_pass_before_red_ceased","first_stop_frame","stop_latency_s","first_pass_frame","observed_early_restart_during_red","observed_held_until_red_ceased"},
            "direction":{"approach_direction"},"divided_other_roadway":{"divided_highway","other_roadway"},
            "officer_control":{"traffic_officer_controlled"},
            "red_cessation_restart":{"observed_motion_after_red_ceased"},
            "premature_restart":{"observed_early_restart_during_red","observed_held_until_red_ceased"}}[variable]
    keys=("approach_direction","divided_highway","other_roadway","traffic_officer_controlled",
          "observed_stop_during_red","observed_pass_before_red_ceased","observed_motion_after_red_ceased",
          "first_stop_frame","stop_latency_s","first_pass_frame","observed_early_restart_during_red",
          "observed_held_until_red_ceased")
    for key in keys:
        if key not in varies and a.get(key)!=b.get(key):raise ValueError("held condition changed: "+key)
    if not any(a.get(key)!=b.get(key) for key in varies):raise ValueError("deliberate comparison variable did not change")
    return {"comparison_complete":True,"variable":variable,"fixed_conditions_checked":[k for k in keys if k not in varies],"legal_conclusion":None}
