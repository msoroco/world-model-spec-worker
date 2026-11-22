"""Emit four exact scene drafts for subsequent Native bundle construction."""
from __future__ import annotations

import json
from pathlib import Path

from bus_route import ROUTES, route
from native_construction import check_road, check_scene


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def build():
    scenes = []
    road = check_road(ROOT / "candidate-red-x-road.xodr")
    for kind in ROUTES:
        scene = {"assignment_id": ASSIGNMENT, "case_id": ASSIGNMENT + "__" + kind,
                 "law_id": "NRS-484B-307-12b", "cell_id": "C147332",
                 "actor": "bus_driver", "layout": "one_way_multilane",
                 "control": "lane_signal", "bus_blueprint_id": "vehicle.mitsubishi.fusorosa",
                 "route": route(kind),
                 "map_source": "candidate-red-x-road.xodr",
                 "map_source_sha256": road["road_sha256"],
                 "signal": {"placement": "over_governed_lane", "facing": "bus_approach",
                            "display": "red_x", "governed_lane_id": "red_lane",
                            "longitudinal_m": 50.0, "lateral_m": -1.8, "height_m": 6.0,
                            "official_device_source": None},
                 "source_requirements": ["original highway source", "original official device record",
                                         "original signal-lane alignment", "original bus blueprint and footprint"],
                 "capture_plan": {"rate_hz": 20, "duration_s": 18,
                                  "cameras": ["overview", "approach", "reference_corner", "driver_reference"]},
                 "preparation_status": "draft_requires_native_and_source_binding",
                 "legal_judgment": "unresolved"}
        path = ROOT / "cases" / kind / "scene.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(scene, indent=2) + "\n")
        check_scene(scene, ROOT / scene["map_source"])
        scenes.append(path)
    return scenes


if __name__ == "__main__":
    for path in build():
        print(path.relative_to(ROOT))
