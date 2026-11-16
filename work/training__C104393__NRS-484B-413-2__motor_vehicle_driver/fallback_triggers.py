"""Source-hashed CPU fallback metrics; synthetic results cannot dispatch Native work."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contained(vertex, radius):
    x,y=vertex
    if not all(math.isfinite(v) for v in (x,y)):raise ValueError("Nonfinite body source")
    if x<=0:return 0<=y<=3.5
    distance=math.hypot(x,y+radius)
    return radius<=distance<=radius+3.5


def evaluate(samples, geometry, pixel_review, *, expected_hashes, source_kind):
    if source_kind not in ("synthetic_cpu_fixture","original_native_capture"):
        raise ValueError("Source provenance missing")
    paths={"native_samples.jsonl":Path(samples),"road_geometry.json":Path(geometry),
           "pixel_review.jsonl":Path(pixel_review)}
    if {name:sha(path) for name,path in paths.items()}!=expected_hashes:
        raise ValueError("source hash mismatch")
    rows=[json.loads(line) for line in paths["native_samples.jsonl"].read_text().splitlines() if line]
    reviews=[json.loads(line) for line in paths["pixel_review.jsonl"].read_text().splitlines() if line]
    geo=json.loads(paths["road_geometry.json"].read_text())
    if len(rows)!=840 or len(reviews)!=840:
        raise ValueError("incomplete Native or pixel source")
    if geo.get("provenance")!=source_kind or geo.get("turn_radius_m") not in (20.0,24.0):
        raise ValueError("map provenance or radius differs")
    lane_link=geo.get("lane_link_confirmed")
    if type(lane_link) is not bool:raise ValueError("Native lane-link observation missing")
    if source_kind=="original_native_capture" and geo.get("native_map_sha256") in (None,"0"*64):
        raise ValueError("original Native map identity missing")
    turn=[i for i,row in enumerate(rows) if row.get("course_change") is True]
    if len(turn)!=1:raise ValueError("one observed turn onset required")
    turn=turn[0]
    exit_index=next((i for i in range(turn+1,len(rows)) if rows[i].get("heading_deg",0)<=-85),None)
    if exit_index is None:raise ValueError("turn exit source missing")
    body_fail=[];errors=[];visible=[]
    for i,(row,review) in enumerate(zip(rows,reviews)):
        if row.get("frame")!=i or review.get("frame")!=i or \
                row.get("native_frame")!=review.get("native_frame"):
            raise ValueError("original pixel/Native frame join differs")
        if type(review.get("signal_and_body_visible")) is not bool:
            raise ValueError("pixel review annotation missing")
        error=row.get("route_error_m")
        if type(error) not in (int,float) or not math.isfinite(error) or error<0:
            raise ValueError("observed route error missing")
        if i<=exit_index:
            body=row.get("native_body_xy_m")
            if not isinstance(body,list) or len(body)!=4 or any(
                    not isinstance(v,list) or len(v)!=2 for v in body):
                raise ValueError("full Native body footprint missing")
            if not all(contained(vertex,geo["turn_radius_m"]) for vertex in body):
                body_fail.append(i)
        if turn<=i<=exit_index:errors.append(error)
        if i<=turn:visible.append(review["signal_and_body_visible"])
    max_error=max(errors);fraction=sum(visible)/len(visible)
    return {"format":"c104393-fallback-trigger-metrics-v1",
        "sources":expected_hashes,"source_kind":source_kind,
        "lane_link_confirmed":lane_link,"body_containment_failure_frames":body_fail,
        "maximum_turn_route_error_m":max_error,
        "visible_signal_and_body_fraction":fraction,
        "fallback1":not lane_link or bool(body_fail),
        "fallback2":max_error>.35,"fallback3":fraction<.95,
        "dispatchable_observation":source_kind=="original_native_capture",
        "physical_success_claimed":False}
