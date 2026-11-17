"""Original-footprint observations for NRS 484B.400(5); no legal cutoff."""
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
            "source_refs":[str(geometry_path),str(body_path)],
            "source_sha256":{str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest()
                             for p in (geometry_path,body_path)},
            "legal_conclusion":None}

def construct_route_targets(geometry_path, approach_offset_m, departure_offset_m):
    """Plan two independently controlled left-curb offsets from original map readback.

    These are controller targets, never an assertion of realized motion or legal
    practicability. The source must supply the inward side and available width
    for both one-way highways, so this function cannot guess a map orientation.
    """
    path=Path(geometry_path)
    g=_load(path)
    if (g.get("source_directionality"),g.get("destination_directionality"),g.get("maneuver")) != ("one_way","one_way","left_turn"):
        raise ValueError("exact one-way-to-one-way left-turn layout missing")
    if not g.get("map_source") or not g.get("intersection_id"):
        raise ValueError("original map provenance or intersection identity missing")
    targets={}
    for name,offset in (("source",approach_offset_m),("destination",departure_offset_m)):
        curb=_line(g.get(name+"_left_curb"))
        normal=g.get(name+"_left_curb_inward_unit")
        width=g.get(name+"_road_width_m")
        if (type(offset) not in (int,float) or type(width) not in (int,float)
                or not 0 < offset < width):
            raise ValueError("curb offset outside source road width: "+name)
        if (not isinstance(normal,list) or len(normal)!=2
                or any(type(v) not in (int,float) for v in normal)
                or abs(hypot(*normal)-1)>.001
                or abs(normal[0]*curb[1]+normal[1]*curb[2])>.001):
            raise ValueError("source inward curb normal missing or not perpendicular: "+name)
        a,dx,dy,_=curb
        targets[name]={"left_curb_offset_setpoint_m":float(offset),
                       "waypoints_xy_m":[[a[0]+t*dx+offset*normal[0],
                                          a[1]+t*dy+offset*normal[1]]
                                         for t in (.2,.8)]}
    return {"intersection_id":g["intersection_id"],"map_source":g["map_source"],
            "geometry_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "approach":targets["source"],"departure":targets["destination"],
            "actual_native_motion_verified":False,"legal_conclusion":None}

CAMERAS=("overview","approach","reference_corner","driver_reference")

def finalize_original_sources(attempt):
    """Derive measured curb streams only from a sealed original-source bundle."""
    root=Path(attempt)
    receipt=_load(root/"curb_source_receipt.json")
    required={"oneway_geometry_original.json","body_ground_original.json",
              "trace.jsonl","video_frames.jsonl"}
    required|={name+".mkv" for name in CAMERAS}
    required|={name+"-frames.jsonl" for name in CAMERAS}
    hashes=receipt.get("source_sha256")
    if not isinstance(hashes,dict) or set(hashes)!=required:
        raise ValueError("original four-camera curb source inventory incomplete")
    for name,expected in hashes.items():
        source=root/name
        if not source.is_file():raise ValueError("Missing required source: "+name)
        if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            raise ValueError("Original curb source SHA-256 mismatch: "+name)
    geometry_path=root/"oneway_geometry_original.json"
    body_path=root/"body_ground_original.json"
    observed=measure(geometry_path,body_path)
    geometry=_load(geometry_path)
    body=_load(body_path)["frames"]
    def lines(name):
        return [json.loads(line) for line in (root/name).read_text().splitlines() if line.strip()]
    trace=lines("trace.jsonl")
    mapping=lines("video_frames.jsonl")
    camera_rows={name:lines(name+"-frames.jsonl") for name in CAMERAS}
    if not body or any(len(rows)!=len(body) for rows in [trace,mapping,*camera_rows.values()]):
        raise ValueError("original curb body/trace/four-camera frame count differs")
    curbs={"approach":_line(geometry["source_left_curb"]),
           "departure":_line(geometry["destination_left_curb"])}
    names=("approach_left_curb_nearest_m","departure_left_curb_nearest_m",
           "original_turn_phase","original_one_way_context","original_left_curb_geometry")
    streams={name:[] for name in names}
    for index,row in enumerate(body):
        frame,time_s=row.get("frame"),row.get("time_s")
        if (type(frame) is not int or type(time_s) not in (int,float)
                or abs(time_s-index*.05)>.005
                or trace[index].get("frame")!=frame
                or mapping[index].get("native_frame")!=frame
                or mapping[index].get("video_frame")!=index
                or abs(trace[index].get("time_s",-1)-time_s)>.005
                or abs(mapping[index].get("time_s",-1)-time_s)>.005):
            raise ValueError("original curb body/trace/frame join differs")
        for name,rows in camera_rows.items():
            if rows[index].get("native_frame")!=frame or abs(rows[index].get("time_s",-1)-time_s)>.005:
                raise ValueError("original curb camera frame join differs: "+name)
        corners=row["ground_corners"]
        if not isinstance(corners,list) or len(corners)!=4:
            raise ValueError("original four-corner footprint missing")
        values={"approach_left_curb_nearest_m":min(abs(_signed(p,curbs["approach"])) for p in corners),
                "departure_left_curb_nearest_m":min(abs(_signed(p,curbs["departure"])) for p in corners),
                "original_turn_phase":row["phase"],
                "original_one_way_context":{"source":"one_way","destination":"one_way","intersection_id":geometry["intersection_id"]},
                "original_left_curb_geometry":{"source":geometry["source_left_curb"],"destination":geometry["destination_left_curb"]}}
        for name,value in values.items():
            streams[name].append({"frame":frame,"time_s":time_s,"phase":row["phase"],"value":value})
    for name,rows in streams.items():
        output=root/(name+".jsonl")
        if output.exists():raise ValueError("derived curb stream already exists: "+name)
        output.write_text("".join(json.dumps(row,allow_nan=False)+"\n" for row in rows))
    return {"case_id":receipt.get("case_id"),"source_sha256":hashes,
            "measurement":observed,"recording_evidence":
            [{"name":name,"reference":name+".jsonl","sha256":hashlib.sha256((root/(name+".jsonl")).read_bytes()).hexdigest()}
             for name in names],
            "actual_native_capture":False,"physical_acceptance_claimed":False,"legal_acceptance_claimed":False}

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--geometry",required=True);ap.add_argument("--body",required=True);ap.add_argument("--output",required=True)
    a=ap.parse_args();Path(a.output).write_text(json.dumps(measure(a.geometry,a.body),indent=2)+"\n")
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
        hashes=r.get("source_sha256",{})
        for source in r["source_refs"]:
            p=Path(source)
            if not p.is_file() or hashes.get(source)!=hashlib.sha256(p.read_bytes()).hexdigest():
                raise ValueError("missing or changed original source: "+source)
    for key in ("subject_id","intersection_id","source_directionality","destination_directionality","maneuver"):
        if a.get(key)!=b.get(key):raise ValueError("fixed geometry or identity changed: "+key)
    if variable=="approach_curb_position":
        fixed,varied="departure_left_curb_nearest_m","approach_left_curb_nearest_m"
    else:
        fixed,varied="approach_left_curb_nearest_m","departure_left_curb_nearest_m"
    if abs(a[fixed]-b[fixed])>.001:raise ValueError("held curb position changed: "+fixed)
    if abs(a[varied]-b[varied])<.001:raise ValueError("deliberate measured curb position did not vary")
    return {"comparison_complete":True,"variable":variable,"fixed_conditions_checked":["subject_id","intersection_id","one-way directionalities",fixed],"legal_conclusion":None}

if __name__=="__main__":main()
