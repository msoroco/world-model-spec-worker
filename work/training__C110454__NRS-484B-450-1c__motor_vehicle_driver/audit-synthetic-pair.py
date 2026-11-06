"""Independent recomputation from saved files, source law and authored route."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((HERE.parents[1] / "inputs" / HERE.name / "assignment.json").read_text())


def main():
    law = ASSIGNMENT["law_record"]["text"]
    if "Within an intersection." not in law or "except when necessary to avoid conflict" not in law:
        raise ValueError("Frozen statutory branch or exception text differs")
    road = ET.fromstring((HERE / "native" / "road.xodr").read_text())
    if len(road.findall("junction/connection")) != 2:
        raise ValueError("Independent authored intersection topology differs")
    outcomes = {}
    for suffix in ("probe_a", "probe_b"):
        path = HERE / "fixtures" / suffix / "native_samples.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != 480: raise ValueError("Saved 480-frame count differs")
        for i, row in enumerate(rows):
            if row["video_frame"] != i or row["native_frame"] != 1000 + i:
                raise ValueError("Independent frame join differs")
            if abs(row["time_s"] - i / 20) > 1e-8:
                raise ValueError("Independent sample clock differs")
            if set(row["exceptions"].values()) != {False}:
                raise ValueError("Exception observation differs")
            if row.get("exception_source") != {"other_traffic_actor_count": 0,
                                               "native_signal_count": 0,
                                               "authored_law_direction_count": 0}:
                raise ValueError("Independent exception source counts differ")
        parked = [row for row in rows if row["speed_m_s"] <= .05]
        if len(parked) != 240: raise ValueError("Sustained deliberate stop differs")
        footprint = parked[-1]["body_xy_m"]
        xs = [p[0] for p in footprint]; ys = [p[1] for p in footprint]
        overlap = max(0, min(max(xs), 7) - max(min(xs), -7)) * \
                  max(0, min(max(ys), 7) - max(min(ys), -7))
        relation = "within_intersection" if overlap > 0 else "outside_intersection"
        expected = "outside_intersection" if suffix == "probe_a" else "within_intersection"
        if relation != expected or (suffix == "probe_b" and overlap < 10):
            raise ValueError("Independent controlled footprint differs")
        outcomes[suffix] = {"relation": relation, "overlap_m2": overlap,
                            "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    print(json.dumps({"passed": True, "scope": "independent synthetic CPU pair audit",
                      "comparison_variable": "intersection_parking_footprint",
                      "law_source_sha256": hashlib.sha256(
                          (HERE.parents[1] / "inputs" / HERE.name / "assignment.json").read_bytes()).hexdigest(),
                      "cases": outcomes}, indent=2))


if __name__ == "__main__": main()
