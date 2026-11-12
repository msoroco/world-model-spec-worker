"""Original-footprint observations for NRS 484B.400(4); no legal cutoff."""
from __future__ import annotations
from math import hypot
import json
import hashlib
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
    if g.get("source_directionality")!="one_way" or g.get("destination_directionality")!="two_directional":
        raise ValueError("exact one-way-to-two-directional layout missing")
    if g.get("maneuver")!="left_turn" or not g.get("intersection_id") or not g.get("map_source"):
        raise ValueError("turn or map-source provenance missing")
    curb=_line(g.get("source_left_curb")); center=_line(g.get("destination_centerline"))
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
    # Positive is left of directed centerline; negative is right. Direction is the entered road's travel direction.
    departure_side=[_signed(p,center) for r in departure for p in corners(r)]
    return {"subject_id":b["subject_id"],"intersection_id":g["intersection_id"],
            "geometry_sha256":hashlib.sha256(Path(geometry_path).read_bytes()).hexdigest(),
            "body_sha256":hashlib.sha256(Path(body_path).read_bytes()).hexdigest(),
            "source_directionality":"one_way","destination_directionality":"two_directional",
            "maneuver":"left_turn","approach_left_curb_nearest_m":min(approach_curb),
            "approach_left_curb_farthest_m":max(approach_curb),
            "approach_left_curb_min_signed_m":min(_signed(p,curb) for r in approach for p in corners(r)),
            "approach_left_curb_max_signed_m":max(_signed(p,curb) for r in approach for p in corners(r)),
            "departure_centerline_min_signed_m":min(departure_side),
            "departure_centerline_max_signed_m":max(departure_side),
            "departure_all_corners_right_of_centerline":max(departure_side)<0,
            "approach_frame_ids":[r["frame"] for r in approach],
            "departure_frame_ids":[r["frame"] for r in departure],
            "source_refs":[str(geometry_path),str(body_path)],"legal_conclusion":None}

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--geometry",required=True);ap.add_argument("--body",required=True);ap.add_argument("--output",required=True)
    a=ap.parse_args();Path(a.output).write_text(json.dumps(measure(a.geometry,a.body),indent=2)+"\n")
if __name__=="__main__":main()
