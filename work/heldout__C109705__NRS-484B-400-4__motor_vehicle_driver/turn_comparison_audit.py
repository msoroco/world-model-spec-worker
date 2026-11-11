"""Independent comparison of measured approach and departure positions."""
import json
from pathlib import Path

def audit(paths,variable):
    if variable not in ("approach_curb_position","departure_centerline_side"):
        raise ValueError("unknown comparison variable")
    if len(paths)!=2: raise ValueError("comparison needs two exact cases")
    rows=[json.loads(Path(p).read_text()) for p in paths]
    for r in rows:
        if len(r.get("source_refs",[]))!=2 or r.get("legal_conclusion") is not None:
            raise ValueError("source-bound measurement missing or legal conclusion asserted")
    for key in ("subject_id","intersection_id","source_directionality","destination_directionality","maneuver"):
        if rows[0].get(key)!=rows[1].get(key): raise ValueError("fixed geometry or identity changed: "+key)
    if variable=="approach_curb_position":
        if rows[0].get("departure_all_corners_right_of_centerline")!=rows[1].get("departure_all_corners_right_of_centerline"):
            raise ValueError("held departure side changed")
        key="approach_left_curb_nearest_m"
    else:
        if abs(rows[0].get("approach_left_curb_nearest_m",-1)-rows[1].get("approach_left_curb_nearest_m",-2))>0.001:
            raise ValueError("held approach curb position changed")
        key="departure_centerline_max_signed_m"
    if abs(rows[0][key]-rows[1][key])<0.001:
        raise ValueError("deliberate measured position did not vary")
    return {"comparison_complete":True,"variable":variable,"fixed_conditions_checked":["subject_id","intersection_id","directionalities","maneuver","held other position"],"legal_conclusion":None}
