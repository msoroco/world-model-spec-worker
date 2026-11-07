"""Independent frozen-cell and six-station CPU geometry audit for C104393."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FROZEN = ROOT / "inputs" / HERE.name / "assignment.json"
GEOMETRY = HERE / "native/geometry.py"
AUTHORED = HERE / "native/authored"
FEET = (90, 100, 110, 290, 300, 310)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    assignment = json.loads(FROZEN.read_text())
    cell = assignment["cell"]
    assert assignment["cell_id"] == "C104393"
    assert {key: cell[key] for key in ("layout", "maneuver", "control")} == {
        "layout": "hill_crest", "maneuver": "turn", "control": "other_vehicle"}
    plan = json.loads((HERE / "case-plan.json").read_text())
    assert plan["law_id"] == "NRS-484B-413-2"
    assert "300 feet" in plan["source_law_text"] and "regardless of the weather" in plan["source_law_text"]
    assert {row["case_id"].rsplit("__", 1)[-1] for row in plan["cases"]} == {str(v) for v in FEET}
    report = json.loads((AUTHORED / "geometry-check.json").read_text())
    assert report["passed"] is True and report["native_executed"] is False
    assert report["frozen_cell"] == {key: cell[key] for key in ("layout", "maneuver", "control")}
    assert report["other_vehicle"]["placement_requires_native_survey"] is True
    route = json.loads((AUTHORED / "route.json").read_text())
    assert len(route) == report["route_points"] and len(route) > 1600
    assert route[0] == [-130.0, -1.75, 0.0]
    assert route[1300] == [0.0, -1.75, 0.0]
    assert math.dist(route[-1][:2], [21.75, 20.0]) < 1e-4
    assert abs(route[650][2] - 2.0) < 1e-8
    assert max(math.dist(a, b) for a, b in zip(route, route[1:])) < 0.101
    document = ET.parse(AUTHORED / "scene.xodr").getroot()
    roads = document.findall("road")
    assert len(roads) == 2 and [r.get("id") for r in roads] == ["1", "2"]
    assert len(roads[0].findall("elevationProfile/elevation")) == 2
    assert roads[1].find("planView/geometry/arc").get("curvature") == "0.05"
    assert all(len(road.findall("lanes/laneSection/right/lane")) == 1 for road in roads)
    stations = report["signal_start_stations_m"]
    assert set(stations) == {str(v) for v in FEET}
    measured = {str(feet): round(130.0 - stations[str(feet)], 6) for feet in FEET}
    for feet in FEET:
        assert abs(measured[str(feet)] - feet * 0.3048) < 1e-5
    assert measured["90"] < 30.48 < measured["110"]
    assert measured["290"] < 91.44 < measured["310"]
    design_path = HERE / "native/candidate-design.json"
    design = json.loads(design_path.read_text())
    assert design["passed"] is True and design["native_executed"] is False
    assert design["measured_trigger_crossings"] is False
    assert design["case_count"] == 6 and design["candidate_count"] == 24
    assert set(design["cases"]) == set(stations)
    for feet, candidates in design["cases"].items():
        assert set(candidates) == {"primary", "fallback1", "fallback2", "fallback3"}
        assert all(row["config"]["signal_start_ft"] == int(feet) for row in candidates.values())
        assert candidates["primary"]["config"]["road_geometry"] == "hill_crest_left_curve_radius_20m"
        assert len({candidates[name]["trigger"]["metric"] for name in (
            "fallback1", "fallback2", "fallback3")}) == 3
    return {"format": "c104393-hill-crest-independent-audit-v1", "passed": True,
            "native_executed": False, "selected": False,
            "scope": "authored CPU geometry and station placement only",
            "source_sha256": sha(FROZEN), "geometry_script_sha256": sha(GEOMETRY),
            "xodr_sha256": sha(AUTHORED / "scene.xodr"),
            "route_sha256": sha(AUTHORED / "route.json"),
            "report_sha256": sha(AUTHORED / "geometry-check.json"),
            "candidate_design_sha256": sha(design_path),
            "measured_pre_turn_distances_m": measured}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
