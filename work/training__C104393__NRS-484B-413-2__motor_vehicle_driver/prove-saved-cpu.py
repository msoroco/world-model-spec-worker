"""Reproducible synthetic saved-sample positive/negative measurement diagnostics."""
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/"native"))
from saved_measure import measure,process
from fallback_triggers import evaluate

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def footprint(x,y,heading_deg):
    angle=math.radians(heading_deg);c=math.cos(angle);s=math.sin(angle)
    return [[round(x+u*c-v*s,6),round(y+u*s+v*c,6)]
            for u,v in ((-2,-.8),(-2,.8),(2,-.8),(2,.8))]

def trigger(paths,source_kind="synthetic_cpu_fixture"):
    expected={name:sha(path) for name,path in paths.items()}
    return evaluate(paths["native_samples.jsonl"],paths["road_geometry.json"],
        paths["pixel_review.jsonl"],expected_hashes=expected,source_kind=source_kind)

def run():
    output=HERE/"synthetic-saved-fixtures"
    output.mkdir(exist_ok=True)
    results=[]
    for feet in (90,100,110,290,300,310):
        onset=520-round(feet*.3048/.25)
        case=output/str(feet);case.mkdir(exist_ok=True)
        source=case/"native_samples.jsonl"
        rows=[]
        for i in range(840):
            if i<=520:
                x,y,heading=-130+i*.25,1.75,0 if i<520 else -1
            else:
                angle=min((i-520)*.25/21.75,math.pi/2)
                x,y=21.75*math.sin(angle),-20+21.75*math.cos(angle)
                heading=-math.degrees(angle)
            rows.append({"frame":i,"native_frame":1000+i,"video_frame":i,
                "time_s":i/20,"ego_xy_m":[x,y],
                "native_body_xy_m":footprint(x,y,heading),"route_error_m":.1,
                "heading_deg":heading,"signal":"left" if i>=onset else "off",
                "course_change":i==520,"area":"any_other_area","weather":"clear_noon"})
        source.write_text("".join(json.dumps(row,separators=(",", ":"))+"\n" for row in rows))
        construction=json.loads((HERE/f"draft-candidates/{feet}/primary/construction.json").read_text())
        config=json.loads(next(f["content"] for f in construction["files"] if f["path"]=="config.json"))
        (case/"config.json").write_text(json.dumps(config,indent=2)+"\n")
        (case/"road_geometry.json").write_text(json.dumps({
            "authored_map_sha256":config["native_request"]["map_sha256"],
            "native_map_sha256":"0"*64,"turn_radius_m":20.0,
            "lane_link_confirmed":True,"provenance":"synthetic_cpu_fixture"},indent=2)+"\n")
        review=case/"pixel_review.jsonl"
        review.write_text("".join(json.dumps({"frame":i,"native_frame":1000+i,
            "signal_and_body_visible":True},separators=(",", ":"))+"\n" for i in range(840)))
        measured=process(case,case/"config.json")
        assert abs(measured["target_error_ft"])<.5
        negative={}
        try:measure(source,"0"*64)
        except ValueError as exc:negative["source_hash_mismatch"]=str(exc)
        else:raise AssertionError("Source hash mutation accepted")
        broken=case/"negative-gap.jsonl"
        broken.write_text("".join(json.dumps(row,separators=(",", ":"))+"\n" for row in rows[:100]+rows[101:]))
        try:measure(broken,sha(broken))
        except ValueError as exc:negative["missing_frame"]=str(exc)
        else:raise AssertionError("Missing frame accepted")
        broken.unlink()
        results.append({"target_ft":feet,"source":str(source.relative_to(HERE)),
            "source_sha256":sha(source),"measured_ft":measured["continuous_signal_distance_ft"],
            "negative":negative})
        paths={"native_samples.jsonl":source,"road_geometry.json":case/"road_geometry.json",
               "pixel_review.jsonl":review}
        baseline=trigger(paths)
        if any(baseline[name] for name in ("fallback1","fallback2","fallback3")):
            raise AssertionError("Synthetic primary triggered a fallback")
        results[-1]["baseline_trigger_metrics"]=baseline
        crossings={}
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp)
            for name in ("fallback1","fallback2","fallback3"):
                modified_rows=json.loads(json.dumps(rows))
                modified_review=[{"frame":i,"native_frame":1000+i,
                    "signal_and_body_visible":True} for i in range(840)]
                if name=="fallback1":modified_rows[550]["native_body_xy_m"][0][1]+=4
                if name=="fallback2":modified_rows[550]["route_error_m"]=.4
                if name=="fallback3":
                    for item in modified_review[:30]:item["signal_and_body_visible"]=False
                changed=temp/(name+"-samples.jsonl")
                changed.write_text("".join(json.dumps(row,separators=(",", ":"))+"\n" for row in modified_rows))
                changed_review=temp/(name+"-review.jsonl")
                changed_review.write_text("".join(json.dumps(row,separators=(",", ":"))+"\n" for row in modified_review))
                altered=dict(paths)
                altered["native_samples.jsonl"]=changed
                altered["pixel_review.jsonl"]=changed_review
                outcome=trigger(altered)
                if [key for key in ("fallback1","fallback2","fallback3") if outcome[key]]!=[name]:
                    raise AssertionError("Fallback crossing is not isolated: "+name)
                crossings[name]={"metric":outcome,
                    "sample_sha256":sha(changed),"pixel_review_sha256":sha(changed_review)}
        results[-1]["isolated_synthetic_crossings"]=crossings
    receipt={"format":"c104393-synthetic-saved-cpu-v1","passed":True,
        "provenance":"synthetic_cpu_fixture","physical_success_claimed":False,
        "cases":results}
    (HERE/"synthetic-saved-cpu-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt))

if __name__=="__main__":run()
