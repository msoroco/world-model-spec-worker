"""Independent 480-frame parking-pair audit of retained synthetic sources."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/"../../.runtime-work/c110454-lvmc-synthetic"
results={}
for case in ("witness_1","witness_2","numeric_1_0","numeric_1_1","numeric_1_2"):
    path=OUT/(case+"-native.json")
    packet=json.loads(path.read_text())
    if packet.get("synthetic_fixture") is not True or len(packet["frames"])!=480:
        raise ValueError("Incomplete synthetic saved source")
    rows=packet["frames"]
    if any(row["video_frame"]!=i or row["native_frame"]!=i or
           abs(row["time_s"]-i*.05)>1e-6 for i,row in enumerate(rows)):
        raise ValueError("Source join differs")
    rest=[r for r in rows if r["speed_m_s"]<=.05]
    if len(rest)!=80 or [r["native_frame"] for r in rest]!=list(range(400,480)):
        raise ValueError("Continuous stopped interval differs")
    distance=min(min(p[0] for p in r["body_xy_m"])-7 for r in rest)
    results[case]={"distance_m":distance,"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
if not results["witness_1"]["distance_m"]>4.572>results["witness_2"]["distance_m"]:
    raise ValueError("Controlled relation differs")
if not results["numeric_1_0"]["distance_m"]<4.572<results["numeric_1_2"]["distance_m"]:
    raise ValueError("Numeric below/above probes differ")
if abs(results["numeric_1_1"]["distance_m"]-4.572)>.001:
    raise ValueError("Numeric boundary probe differs")
if any(json.loads((OUT/(case+"-missing-frame.json")).read_text())["frames"][200]["native_frame"]!=-1
       for case in results):
    raise ValueError("Damaged-source negatives missing")
print(json.dumps({"passed":True,"synthetic_only":True,"results":results,"physical_observation":False},sort_keys=True))
