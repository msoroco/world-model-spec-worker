"""Verify selected C104538 constructions encode both frozen location alternatives."""
import copy
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FT_M = 0.3048


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def assess(construction, case_id, candidate_id):
    require(construction.get("case_id") == case_id, "Wrong selected case")
    files = {item["path"]: item["content"] for item in construction["files"]}
    require({"authored_road.xodr", "config.json", "runner.py", "measure_native.py"} <= set(files),
            "Construction omits original road or measurement source")
    config = json.loads(files["config.json"])
    require(config.get("case_id") == case_id and config.get("candidate_id") == candidate_id,
            "Configuration selects another candidate")
    channels = {item["name"] for item in config["recording_description"]["channels"]}
    require({"drv.u_turn", "st.curvature", "st.grade", "st.crest", "st.sight_distance",
             "rel.oncoming", "drv.approaching", "kin.position"} <= channels,
            "Statutory observation channels omitted")
    road = ET.fromstring(files["authored_road.xodr"]).find("road")
    require(road is not None, "No authored road")
    length = float(road.attrib["length"])
    geometry = road.find("planView/geometry")
    arc = road.find("planView/geometry/arc")
    elevation = road.find("elevationProfile/elevation")
    require(geometry is not None and arc is not None and elevation is not None,
            "Curve or crest alternative missing")
    curvature = float(arc.attrib["curvature"])
    require(math.isfinite(curvature) and abs(curvature) > 1e-6,
            "Curve curvature is zero")
    s = float(elevation.attrib["s"])
    a, b, c, d = (float(elevation.attrib[name]) for name in ("a", "b", "c", "d"))
    require(all(math.isfinite(x) for x in (length, s, a, b, c, d)) and
            length > 2 * 500 * FT_M and c < 0 and abs(d) < 1e-12,
            "Crest shape or two-direction 500-foot route missing")
    crest_station = s - b / (2*c)
    height = a + b*(crest_station-s) + c*(crest_station-s)**2
    require(500*FT_M <= crest_station <= length-500*FT_M and height > a and
            abs(crest_station-200) < 1e-6 and
            float(geometry.attrib["length"]) == length,
            "Crest not at turn or route insufficient in both directions")
    return {"curve_curvature_per_m": curvature, "crest_station_m": crest_station,
            "crest_height_m": height, "approach_left_m": crest_station,
            "approach_right_m": length-crest_station,
            "two_direction_500_ft_route_authored": True,
            "native_loaded": False, "original_visibility_proven": False}


def main():
    assignment_path = ROOT / "inputs" / HERE.name / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    law = assignment["law_record"]["text"]
    review_path = HERE / "statutory-review.json"
    review = json.loads(review_path.read_text())
    require(review["law_text"] == law and
            set(review["location_alternatives"]) == {"curve", "crest"} and
            "upon any curve" in law and "near the crest of a grade" in law and
            "either direction within 500 feet" in law,
            "Frozen statutory alternatives changed")
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    require(len(manifest["cases"]) == 3, "Selected boundary coverage changed")
    rows = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        for candidate in [entry, *entry["candidates"]]:
            path = HERE / candidate["construction"]
            require(sha(path) == candidate["construction_sha256"],
                    "Selected construction hash changed")
            candidate_id = candidate.get("id", "primary")
            result = assess(json.loads(path.read_text()), case_id, candidate_id)
            rows.append({"case_id": case_id, "candidate_id": candidate_id,
                         "construction_sha256": sha(path), **result})
    require(len(rows) == 12, "Selected candidate count changed")
    require(len({(r["curve_curvature_per_m"], r["crest_station_m"], r["crest_height_m"])
                 for r in rows}) == 1, "Fixed curve/crest geometry changed across candidates")
    sample = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())
    rejected = []
    for name, mutate in (
        ("removed_arc", lambda x: x["files"].__setitem__(next(i for i,v in enumerate(x["files"])
             if v["path"] == "authored_road.xodr"),
             {"path":"authored_road.xodr", "content": next(v["content"] for v in x["files"]
                if v["path"] == "authored_road.xodr").replace('<arc curvature="0.002" />', '')})),
        ("wrong_candidate", lambda x: x["files"].__setitem__(next(i for i,v in enumerate(x["files"])
             if v["path"] == "config.json"),
             {"path":"config.json", "content":next(v["content"] for v in x["files"]
                if v["path"] == "config.json").replace('"candidate_id": "primary"', '"candidate_id": "fallback1"')})),
    ):
        damaged = copy.deepcopy(sample)
        mutate(damaged)
        try:
            assess(damaged, manifest["cases"][0]["case_id"], "primary")
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("Damaged statutory alternative accepted: " + name)
    report = {"format": "c104538-selected-statutory-alternatives-cpu-v1",
              "assignment_sha256": sha(assignment_path), "statutory_review_sha256": sha(review_path),
              "manifest_sha256": sha(manifest_path), "candidate_count": len(rows),
              "candidate_assessments": rows, "mutations_rejected": rejected,
              "native_loaded_or_visibility_proven": False, "legal_verdict_claimed": False}
    (HERE / "update024-statutory-alternatives-proof.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"candidates": len(rows), "mutations_rejected": rejected,
                      "native_loaded_or_visibility_proven": False}))


if __name__ == "__main__":
    main()
