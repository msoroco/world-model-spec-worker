"""Source-hashed saved signal distance; no authored target substitutes for pose."""
import hashlib
import json
import math
from pathlib import Path


def measure(source, expected_sha256, *, expected_frames=840, expected_weather="clear_noon"):
    source=Path(source)
    if not source.is_file():raise ValueError("Missing required source: native_samples.jsonl")
    raw=source.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=expected_sha256:raise ValueError("source hash mismatch")
    rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows)!=expected_frames:raise ValueError("incomplete saved source interval")
    first_time=rows[0].get("time_s")
    prior_native=-1
    for index,row in enumerate(rows):
        frame=row.get("native_frame")
        if row.get("frame")!=index or row.get("video_frame")!=index or \
                type(frame) is not int or frame<=prior_native:
            raise ValueError("Native/video frame discontinuity")
        prior_native=frame
        time=row.get("time_s")
        if type(time) not in (int,float) or not math.isfinite(time) or \
                abs(time-first_time-index/20)>1e-3:
            raise ValueError("Native time discontinuity")
        if row.get("area")!="any_other_area" or row.get("weather")!=expected_weather:
            raise ValueError("saved area/weather context differs")
        if row.get("signal") not in ("left","off") or type(row.get("course_change")) is not bool:
            raise ValueError("observed signal or course-change state missing")
        xy=row.get("ego_xy_m")
        if not isinstance(xy,list) or len(xy)!=2 or not all(
                type(v) in (int,float) and math.isfinite(v) for v in xy):
            raise ValueError("observed ego pose missing")
    turns=[i for i,row in enumerate(rows) if row["course_change"]]
    if len(turns)!=1 or turns[0]<2:raise ValueError("one observed course change required")
    turn=turns[0]
    start=turn
    while start>0 and rows[start-1]["signal"]=="left":start-=1
    if start==0 or rows[turn]["signal"]!="left" or rows[start-1]["signal"]!="off":
        raise ValueError("continuous signal onset not captured")
    if rows[turn-1]["heading_deg"]<=-1 or rows[min(turn+25,len(rows)-1)]["heading_deg"]>=-10:
        raise ValueError("measured heading transition missing")
    distance=0.0
    for index in range(start+1,turn+1):
        a,b=rows[index-1]["ego_xy_m"],rows[index]["ego_xy_m"]
        step=math.dist(a,b)
        if not 0<step<1:raise ValueError("implausible saved path step")
        distance+=step
    return {"format":"c104393-saved-signal-v1","source_sha256":digest,
        "sample_count":len(rows),"onset_frame":start,"course_change_frame":turn,
        "continuous_signal_distance_ft":distance/.3048,"threshold_ft":300,
        "area":"any_other_area","weather":expected_weather,
        "physical_success_claimed":False,"legal_verdict_claimed":False}


def process(attempt, config):
    attempt=Path(attempt)
    source=attempt/"native_samples.jsonl"
    if not source.is_file():raise ValueError("Missing required source: native_samples.jsonl")
    config=json.loads(Path(config).read_text())
    measured=measure(source,hashlib.sha256(source.read_bytes()).hexdigest(),
        expected_frames=config["duration_s"]*config["rate_hz"],
        expected_weather=config["native_request"]["weather"])
    if config["native_request"]["area"]!="any_other_area":
        raise ValueError("exact area request differs")
    geometry=attempt/"road_geometry.json"
    if not geometry.is_file():raise ValueError("Missing required source: road_geometry.json")
    geo=json.loads(geometry.read_text())
    if geo.get("authored_map_sha256")!=config["native_request"]["map_sha256"]:
        raise ValueError("saved map differs from exact request")
    measured["road_geometry_sha256"]=hashlib.sha256(geometry.read_bytes()).hexdigest()
    measured["target_distance_ft"]=config["native_request"]["signal_start_ft"]
    measured["target_error_ft"]=measured["continuous_signal_distance_ft"]-measured["target_distance_ft"]
    return measured


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--attempt",type=Path,required=True)
    parser.add_argument("--config",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=process(args.attempt,args.config or args.attempt/"config.json")
    with args.output.open("x") as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
        stream.write("\n")
