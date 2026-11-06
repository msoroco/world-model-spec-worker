"""Independent authored road/parking-station audit."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
road=HERE/"native/road.xodr"
root=ET.parse(road).getroot()
roads={int(r.attrib["id"]):r for r in root.findall("road")}
if set(roads)!={1,2,3,4,13,14}:raise ValueError("Same-cell intersection roads differ")
if len(root.findall("junction/connection"))!=2:raise ValueError("Intersection connectors differ")
bay=roads[2].find("objects/object[@type='parkingSpace']")
if bay is None or float(bay.attrib["length"])!=27:raise ValueError("Parking bay missing")
results={}
for case,expected_x in (("witness_1",25.0),("witness_2",13.5),
                        ("numeric_1_0",13.5),("numeric_1_1",14.172),
                        ("numeric_1_2",15.0)):
    path=HERE/"native/routes"/(case+".json")
    points=json.loads(path.read_text())
    if points[0]!=[-70.0,-1.75] or points[-1]!=[expected_x,-5.25]:
        raise ValueError("Controlled route endpoints differ")
    if max(math.dist(a,b) for a,b in zip(points,points[1:]))>=.15:
        raise ValueError("Route discontinuity")
    distance=expected_x-2.6-7
    results[case]={"parked_body_distance_m":distance,
                   "route_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
if not results["witness_1"]["parked_body_distance_m"]>4.572>results["witness_2"]["parked_body_distance_m"]:
    raise ValueError("Authored body stations do not bracket 15 feet")
if not results["numeric_1_0"]["parked_body_distance_m"]<4.572<results["numeric_1_2"]["parked_body_distance_m"]:
    raise ValueError("Numeric below/above stations do not bracket 15 feet")
if abs(results["numeric_1_1"]["parked_body_distance_m"]-4.572)>.001:
    raise ValueError("Exact boundary station differs")
print(json.dumps({"passed":True,"road_sha256":hashlib.sha256(road.read_bytes()).hexdigest(),
                  "case_results":results,"native_observed":False,"legal_verdict":None},sort_keys=True))
