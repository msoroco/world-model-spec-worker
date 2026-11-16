"""Source-bound school-bus approach observations; no legal conclusion."""
from __future__ import annotations
import json
import hashlib
import math
from pathlib import Path


def _read(path):
    path=Path(path)
    if not path.is_file(): raise ValueError("missing original school-bus source: "+str(path))
    return json.loads(path.read_text())


def measure(context_path, signal_path, motion_path):
    context, signal, motion=map(_read,(context_path,signal_path,motion_path))
    source_hashes={name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in
                   (("context",context_path),("signal",signal_path),("motion",motion_path))}
    if context.get("approach_direction") not in ("meeting","overtaking"):
        raise ValueError("meeting or overtaking direction required")
    if not context.get("road_source") or not context.get("bus_equipment_source") or not context.get("pupil_stop_source"):
        raise ValueError("road, equipment and pupil-stop original sources required")
    if context.get("bus_stopped_for_pupils") is not True or context.get("bus_required_equipment") is not True:
        raise ValueError("bus triggering conditions missing")
    if context.get("divided_highway") not in (True,False) or context.get("other_roadway") not in (True,False):
        raise ValueError("divided-roadway premises required")
    if context["other_roadway"] and not context["divided_highway"]:
        raise ValueError("other roadway requires divided highway")
    if context.get("traffic_officer_controlled") not in (True,False) or not context.get("officer_control_source"):
        raise ValueError("officer-control exception source required")
    if context.get("legal_conclusion") is not None:
        raise ValueError("source cannot assert legal conclusion")
    if not context.get("subject_id") or not context.get("bus_id"):
        raise ValueError("subject and bus identities required")
    if signal.get("bus_id")!=context.get("bus_id") or not signal.get("source"):
        raise ValueError("bus signal identity or original source missing")
    red_on,red_off=signal.get("red_on_frame"),signal.get("red_off_frame")
    if type(red_on) is not int or type(red_off) is not int or red_on>=red_off:
        raise ValueError("flashing-red interval missing")
    if signal.get("front_visible") is not True or signal.get("rear_visible") is not True:
        raise ValueError("front and rear red visibility source condition missing")
    rows=motion.get("frames")
    if not isinstance(rows,list) or len(rows)<3: raise ValueError("original motion span missing")
    rate=motion.get("rate_hz")
    if type(rate) not in (int,float) or not math.isfinite(rate) or rate<=0:
        raise ValueError("original motion frame rate required")
    ids=[r.get("frame") for r in rows]
    if any(type(i) is not int for i in ids) or ids!=sorted(set(ids)):
        raise ValueError("motion frame identities unordered or repeated")
    if not (ids[0]<=red_on<red_off<=ids[-1]):
        raise ValueError("motion does not cover red onset and cessation")
    if red_on not in ids or red_off not in ids:
        raise ValueError("red onset and cessation need original motion frames")
    if any(r.get("subject_id")!=context.get("subject_id") or type(r.get("speed_mps")) not in (int,float) or not math.isfinite(r["speed_mps"]) or r["speed_mps"]<0 or type(r.get("passed_bus")) is not bool for r in rows):
        raise ValueError("original subject motion or pass-state missing")
    active=[r for r in rows if red_on<=r["frame"]<red_off]
    if len(active)<2: raise ValueError("insufficient motion while red flashes")
    if any(r["passed_bus"] for r in rows if r["frame"]<=red_on):
        raise ValueError("bus already passed when red starts")
    if any(a["passed_bus"] and not b["passed_bus"] for a,b in zip(rows,rows[1:])):
        raise ValueError("original pass-state reverses")
    first_stop=next((r["frame"] for r in active if r["speed_mps"]<=.1),None)
    first_pass=next((r["frame"] for r in rows if r["passed_bus"]),None)
    early_restart=(first_stop is not None and
                   any(r["speed_mps"]>.1 for r in active if r["frame"]>first_stop))
    pass_before_off=first_pass is not None and first_pass<red_off
    return {"subject_id":context["subject_id"],"bus_id":context["bus_id"],
            "approach_direction":context["approach_direction"],"divided_highway":context["divided_highway"],
            "other_roadway":context["other_roadway"],"traffic_officer_controlled":context["traffic_officer_controlled"],
            "red_on_frame":red_on,"red_off_frame":red_off,
            "motion_rate_hz":rate,
            "first_stop_frame":first_stop,
            "stop_latency_s":None if first_stop is None else (first_stop-red_on)/rate,
            "first_pass_frame":first_pass,
            "observed_stop_during_red":first_stop is not None,
            "observed_pass_before_red_ceased":pass_before_off,
            "observed_early_restart_during_red":early_restart,
            "observed_held_until_red_ceased":first_stop is not None and not early_restart and not pass_before_off,
            "observed_motion_after_red_ceased":any(r["speed_mps"]>.5 for r in rows if r["frame"]>=red_off),
            "active_frame_ids":[r["frame"] for r in active],
            "source_refs":[str(context_path),str(signal_path),str(motion_path)],
            "source_sha256":source_hashes,"legal_conclusion":None}


def main():
    import argparse
    a=argparse.ArgumentParser()
    for k in ("context","signal","motion","output"):a.add_argument("--"+k,required=True)
    x=a.parse_args();Path(x.output).write_text(json.dumps(measure(x.context,x.signal,x.motion),indent=2)+"\n")
if __name__=="__main__":main()
