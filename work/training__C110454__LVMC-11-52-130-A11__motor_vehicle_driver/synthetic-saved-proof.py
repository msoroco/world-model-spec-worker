"""Local 480-frame source-shaped parking measurement integration."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("measure_park",HERE/"native/measure_park.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
OUT=HERE/"../../.runtime-work/c110454-lvmc-synthetic"


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results={}
    for case in ("witness_1","witness_2","numeric_1_0","numeric_1_1","numeric_1_2"):
        route=json.loads((HERE/"native/routes"/(case+".json")).read_text())
        frames=[]
        for i in range(480):
            x,y=route[min(round(i*(len(route)-1)/399),len(route)-1)]
            frames.append({"video_frame":i,"native_frame":i,"time_s":round(i*.05,4),
                           "body_xy_m":[[x-2.6,y-1.1],[x-2.6,y+1.1],[x+2.6,y+1.1],[x+2.6,y-1.1]],
                           "speed_m_s":4.0 if i<400 else 0.0})
        packet={"source_kind":"native_frame_schema","intersection_boundary_source":"native_map_readback",
                "intersection_entry_boundary_x_m":7.0,"synthetic_fixture":True,"frames":frames}
        source=OUT/(case+"-native.json");source.write_text(json.dumps(packet))
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        result=module.measure(source,digest)
        relation={"witness_1":"outside_15_ft","witness_2":"within_15_ft",
                  "numeric_1_0":"within_15_ft","numeric_1_1":"boundary_unresolved",
                  "numeric_1_2":"outside_15_ft"}[case]
        if result["sampled_relation"]!=relation:raise ValueError("Controlled parking relation differs")
        negative=OUT/(case+"-missing-frame.json")
        bad=json.loads(source.read_text());bad["frames"][200]["native_frame"]=-1
        negative.write_text(json.dumps(bad))
        try:module.measure(negative,hashlib.sha256(negative.read_bytes()).hexdigest())
        except ValueError as error:
            if "join" not in str(error):raise
        else:raise ValueError("Missing-frame negative passed")
        results[case]=result
    print(json.dumps({"passed":True,"synthetic_only":True,"frames_per_case":480,
                      "missing_join_negatives_rejected":len(results),"results":results},sort_keys=True))


if __name__=="__main__":main()
