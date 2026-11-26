"""Build bounded synthetic source-shaped recipes for pinned CPU compatibility.

The neutral graph/video envelope is borrowed from an already passing CPU
fixture. Pedestrian positions and curb entry are generated here. No fixture
byte is an original recording or proof of physical/legal realization.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from curb_entry import CASES
from delivery_audit import ASSIGNMENT


HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
BASE = REPO / "work/testing__C147344__NRS-484B-627-1b__motor_vehicle_driver/cases/slow_middle_follower/diagnostic-spec.json"
MAP = REPO / "work/testing__C147344__NRS-484B-627-1b__motor_vehicle_driver/diagnostic-map.xodr"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n",
                    encoding="utf-8")


def scene(case):
    endpoint = [1, -3] if case.route_kind == "curb" else \
        [0, -1] if case.route_kind == "road_only" else [0, 0]
    item = {"cell_id": "C228096", "actor": "pedestrian",
            "pedestrian_person": True, "vehicle_qualifies": True,
            "driver_in_control": True, "action": case.action,
            "vehicle_gap": case.vehicle_gap, "route_kind": case.route_kind,
            "road_rect_m": [-10, -2, 10, 2],
            "vehicle_path_rect_m": [-10, -.5, 10, .5],
            "curb_start_xy": [0, -3], "departure_frame": 100,
            "pedestrian_route_xy": [[0, -3], endpoint],
            "vehicle_route_xy": [[-30, 0], [10, 0]] if case.vehicle_gap == "far"
                                else [[-10, 0], [10, 0]],
            "vehicle_id": "synthetic-car", "driver_id": "synthetic-driver"}
    for name in ("pedestrian_identity", "curb_safety", "road_boundary",
                 "vehicle_path", "vehicle_motion", "driver_control",
                 "pedestrian_route", "departure_timing", "introductory_exceptions"):
        item[name + "_source_sha256"] = "a" * 64
    return item


def motion(case, item):
    rows = []
    for index in range(900):
        y = -3 if index < 100 or case.route_kind == "curb" else \
            -1 if case.route_kind == "road_only" or index < 200 else 0
        row = {"original_frame": index, "time_s": index / 20,
               "pedestrian_id": "synthetic-ped", "vehicle_id": "synthetic-car",
               "action": case.action, "pedestrian_xy": [0, y],
               "vehicle_xy": [2 if case.vehicle_gap == "close" else 20, 0],
               "pedestrian_speed_mps": 0 if index < 100 else 2 if case.action == "run" else 1,
               "vehicle_speed_mps": 5}
        for name in ("frame", "pedestrian_motion", "vehicle_motion",
                     "road_boundary", "curb_safety", "vehicle_path",
                     "driver_control", "introductory_exceptions"):
            row[name + "_source_sha256"] = "a" * 64
        rows.append(row)
    return rows


def main():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    map_data = MAP.read_bytes()
    map_path = HERE / "diagnostic-map.xodr"
    map_path.write_bytes(map_data)
    for case in CASES:
        case_id = ASSIGNMENT + "__" + case.name
        spec = json.loads(json.dumps(base))
        item = scene(case)
        rows = motion(case, item)
        spec["files"].pop("relation.json", None)
        spec["files"]["site.json"] = json.dumps({"diagnostic_fixture": True,
            "reviewed_original_site": False, "scenes": {case.name: item}},
            separators=(",", ":")) + "\n"
        spec["files"]["trace.json"] = json.dumps({"case_id": case_id,
            "diagnostic_fixture": True, "frames": rows}, separators=(",", ":")) + "\n"
        native_rows = []
        evidence_rows = []
        for index, line in enumerate(spec["files"]["trace.jsonl"].splitlines()):
            value = json.loads(line)
            y = rows[index]["pedestrian_xy"][1]
            value["position_m"] = [0, y, 0]
            value["position"] = {"x": 0, "y": y, "z": 0}
            value["speed_mps"] = rows[index]["pedestrian_speed_mps"]
            value["speed_mph"] = value["speed_mps"] * 2.2369362921
            value["velocity_mps"] = [0, value["speed_mps"], 0]
            native_rows.append(json.dumps(value, separators=(",", ":")))
        spec["files"]["trace.jsonl"] = "\n".join(native_rows) + "\n"
        for index, line in enumerate(spec["files"]["capture/evidence.jsonl"].splitlines()):
            value = json.loads(line)
            y = rows[index]["pedestrian_xy"][1]
            value["ego"]["position_m"] = [0, y, 0]
            value["ego"]["speed_mps"] = rows[index]["pedestrian_speed_mps"]
            value["ego"]["body_vertices_m"] = [[x, y + dy, z]
                for x in (-.3, .3) for dy in (-.3, .3) for z in (0, 1.8)]
            evidence_rows.append(json.dumps(value, separators=(",", ":")))
        spec["files"]["capture/evidence.jsonl"] = "\n".join(evidence_rows) + "\n"
        spec["files"]["capture/recorder_info.txt"] = \
            "Create 11: walker.pedestrian.0001 (synthetic) at (0, -3, 0)\n"
        spec["files"]["acquisition-provenance.json"] = \
            '{"provenance_kind":"synthetic_fixture","diagnostic_fixture":true}\n'
        manifest = json.loads(spec["files"]["capture/manifest.json"])
        manifest["case_id"] = case_id
        manifest["sources"] = {"road.xodr": sha_bytes(map_data),
                               "trace.jsonl": sha_bytes(spec["files"]["trace.jsonl"].encode())}
        spec["files"]["capture/manifest.json"] = json.dumps(manifest, separators=(",", ":")) + "\n"
        spec["files"].pop("road.xodr", None)
        directory = HERE / "cases" / case.name
        spec_path = directory / "diagnostic-spec.json"
        write(spec_path, spec)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "road.xodr",
                               "source": "work/" + ASSIGNMENT + "/diagnostic-map.xodr",
                               "sha256": sha_bytes(map_data)}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha_bytes(spec_path.read_bytes())}}
        write(directory / "diagnostic-recipe.json", recipe)
        if spec_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("diagnostic spec exceeds returned file limit")
    print("Built five bounded synthetic diagnostic recipes")


if __name__ == "__main__":
    main()
