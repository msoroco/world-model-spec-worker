"""Independent fixed-condition comparison for both left-curb clauses."""
import json
from pathlib import Path

def audit(paths,variable):
    if variable not in ("approach_curb_position","turn_departure_curb_position") or len(paths)!=2:
        raise ValueError("two exact cases and known comparison variable required")
    a,b=[json.loads(Path(p).read_text()) for p in paths]
    for r in (a,b):
        if len(r.get("source_refs",[]))!=2 or r.get("legal_conclusion") is not None:
            raise ValueError("source-bound original measurement missing or legal conclusion asserted")
    for key in ("subject_id","intersection_id","source_directionality","destination_directionality","maneuver"):
        if a.get(key)!=b.get(key):raise ValueError("fixed geometry or identity changed: "+key)
    if variable=="approach_curb_position":
        fixed,varied="departure_left_curb_nearest_m","approach_left_curb_nearest_m"
    else:
        fixed,varied="approach_left_curb_nearest_m","departure_left_curb_nearest_m"
    if abs(a[fixed]-b[fixed])>.001:raise ValueError("held curb position changed: "+fixed)
    if abs(a[varied]-b[varied])<.001:raise ValueError("deliberate measured curb position did not vary")
    return {"comparison_complete":True,"variable":variable,"fixed_conditions_checked":["subject_id","intersection_id","one-way directionalities",fixed],"legal_conclusion":None}
