"""Original-footprint observations for NRS 484B.400(5); no legal cutoff."""
from __future__ import annotations
from math import hypot
import json
from pathlib import Path

def _load(p):
    p=Path(p)
    if not p.is_file(): raise ValueError("missing required geometry source: "+str(p))
    return json.loads(p.read_text())

def _line(points):
    if not isinstance(points,list) or len(points)!=2: raise ValueError("line needs two original map points")
    a,b=points
    if any(type(v) not in (int,float) for p in points for v in p) or len(a)!=2 or len(b)!=2:
        raise ValueError("invalid map point")
    dx,dy=b[0]-a[0],b[1]-a[1]
    length=hypot(dx,dy)
    if length < 1: raise ValueError("degenerate map reference line")
    return a,dx,dy,length

def _signed(point,line):
    a,dx,dy,length=line
    return (dx*(point[1]-a[1])-dy*(point[0]-a[0]))/length

def measure(geometry_path, body_path):
    g,b=_load(geometry_path),_load(body_path)
    if g.get("source_directionality")!="one_way" or g.get("destination_directionality")!="one_way":
        raise ValueError("exact one-way-to-one-way layout missing")
    if g.get("maneuver")!="left_turn" or not g.get("intersection_id") or not g.get("map_source"):
        raise ValueError("turn or map-source provenance missing")
    curb=_line(g.get("source_left_curb")); destination_curb=_line(g.get("destination_left_curb"))
    rows=b.get("frames")
    if not isinstance(rows,list) or not rows: raise ValueError("original body footprint frames missing")
    indices=[r.get("frame") for r in rows]
    if any(type(i) is not int for i in indices) or indices!=sorted(set(indices)):
        raise ValueError("body frame identities unordered or repeated")
    if not b.get("subject_id") or any(r.get("subject_id")!=b["subject_id"] for r in rows):
        raise ValueError("body footprint subject mismatch")
    approach=[r for r in rows if r.get("phase")=="approach"]
    departure=[r for r in rows if r.get("phase")=="leaving_intersection"]
    if not approach or not departure or approach[-1]["frame"]>=departure[0]["frame"]:
        raise ValueError("approach and leaving-intersection phases absent or reversed")
    def corners(row):
        p=row.get("ground_corners")
        if not isinstance(p,list) or len(p)!=4 or any(not isinstance(x,list) or len(x)!=2 or any(type(v) not in (int,float) for v in x) for x in p):
            raise ValueError("four original ground body corners required")
        return p
    approach_curb=[abs(_signed(p,curb)) for r in approach for p in corners(r)]
    departure_curb=[abs(_signed(p,destination_curb)) for r in departure for p in corners(r)]
    return {"subject_id":b["subject_id"],"intersection_id":g["intersection_id"],
            "source_directionality":"one_way","destination_directionality":"one_way",
            "maneuver":"left_turn","approach_left_curb_nearest_m":min(approach_curb),
            "approach_left_curb_farthest_m":max(approach_curb),
            "departure_left_curb_nearest_m":min(departure_curb),
            "departure_left_curb_farthest_m":max(departure_curb),
            "approach_frame_ids":[r["frame"] for r in approach],
            "departure_frame_ids":[r["frame"] for r in departure],
            "source_refs":[str(geometry_path),str(body_path)],"legal_conclusion":None}

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--geometry",required=True);ap.add_argument("--body",required=True);ap.add_argument("--output",required=True)
    a=ap.parse_args();Path(a.output).write_text(json.dumps(measure(a.geometry,a.body),indent=2)+"\n")
if __name__=="__main__":main()
