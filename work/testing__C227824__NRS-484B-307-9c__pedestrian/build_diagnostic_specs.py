"""Build bounded synthetic signal/entry fixtures for pinned CPU compatibility."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ped_entry import CASES
from delivery_audit import ASSIGNMENT, SOURCES

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
BASE = REPO / "work/testing__C228096__NRS-484B-283-1b__pedestrian/cases/close_walk_into_path/diagnostic-spec.json"
MAP = REPO / "work/testing__C228096__NRS-484B-283-1b__pedestrian/diagnostic-map.xodr"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")


def scene(case):
    item = {"cell_id": "C227824", "actor": "pedestrian",
            "official_vehicle_signal": True, "steady_red": True,
            "green_turn_arrow": True, "movement": case.movement,
            "other_device_display": case.other_device_display,
            "pedestrian_route_xy": [[-3, 0], [-1, 0], [2, 0]],
            "highway_boundary_line_xy": [[0, -2], [0, 2]], "inside_sign": -1,
            "start_signed_boundary_m": -2, "signal_facing_xy": [10, 0]}
    for name in SOURCES:
        item[name + "_source_sha256"] = "a" * 64
    return item


def motion(case, item):
    rows = []
    for index in range(900):
        signed = 1 if case.movement == "enter" and index >= 120 else -2
        row = {"original_frame": index, "time_s": index / 20,
               "pedestrian_id": "synthetic-ped", "person_afoot": True,
               "facing_signal": True, "official_steady_red": True,
               "official_green_turn_arrow": True,
               "other_device_display": case.other_device_display,
               "body_nearest_signed_boundary_m": signed,
               "pedestrian_xy": [1 if signed > 0 else -3, 0]}
        for name in ("source", "pedestrian_body", "pedestrian_motion",
                     "highway_boundary", "signal_display", "other_device_display",
                     "facing_orientation"):
            row[name + "_sha256"] = "a" * 64
        row["highway_boundary_source_sha256"] = item["highway_boundary_source_sha256"]
        rows.append(row)
    return rows


def main():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    map_data = MAP.read_bytes()
    map_path = HERE / "diagnostic-map.xodr"
    map_path.write_bytes(map_data)
    for case in CASES:
        case_id = ASSIGNMENT + "__" + case.case_id
        spec = json.loads(json.dumps(base))
        item = scene(case)
        rows = motion(case, item)
        spec["files"]["site.json"] = json.dumps({"diagnostic_fixture": True,
            "reviewed_original_site": False, "scenes": {case.case_id: item}},
            separators=(",", ":")) + "\n"
        spec["files"]["trace.json"] = json.dumps({"case_id": case_id,
            "diagnostic_fixture": True, "frames": rows}, separators=(",", ":")) + "\n"
        native_rows = []
        evidence_rows = []
        for index, line in enumerate(spec["files"]["trace.jsonl"].splitlines()):
            value = json.loads(line)
            x = rows[index]["pedestrian_xy"][0]
            value["position_m"] = [x, 0, 0]
            value["position"] = {"x": x, "y": 0, "z": 0}
            value["speed_mps"] = 0 if index < 120 or case.movement == "wait" else 1
            value["speed_mph"] = value["speed_mps"] * 2.2369362921
            value["velocity_mps"] = [value["speed_mps"], 0, 0]
            native_rows.append(json.dumps(value, separators=(",", ":")))
        spec["files"]["trace.jsonl"] = "\n".join(native_rows) + "\n"
        for index, line in enumerate(spec["files"]["capture/evidence.jsonl"].splitlines()):
            value = json.loads(line)
            x = rows[index]["pedestrian_xy"][0]
            value["ego"]["position_m"] = [x, 0, 0]
            value["ego"]["speed_mps"] = 0 if index < 120 or case.movement == "wait" else 1
            value["ego"]["body_vertices_m"] = [[x + dx, dy, z]
                for dx in (-.3, .3) for dy in (-.3, .3) for z in (0, 1.8)]
            evidence_rows.append(json.dumps(value, separators=(",", ":")))
        spec["files"]["capture/evidence.jsonl"] = "\n".join(evidence_rows) + "\n"
        spec["files"]["capture/recorder_info.txt"] = \
            "Create 11: walker.pedestrian.0001 (synthetic) at (-3, 0, 0)\n"
        spec["files"]["acquisition-provenance.json"] = \
            '{"provenance_kind":"synthetic_fixture","diagnostic_fixture":true}\n'
        manifest = json.loads(spec["files"]["capture/manifest.json"])
        manifest["case_id"] = case_id
        manifest["sources"] = {"road.xodr": sha_bytes(map_data),
                               "trace.jsonl": sha_bytes(spec["files"]["trace.jsonl"].encode())}
        spec["files"]["capture/manifest.json"] = json.dumps(manifest, separators=(",", ":")) + "\n"
        spec["files"].pop("road.xodr", None)
        directory = HERE / "cases" / case.case_id
        spec_path = directory / "diagnostic-spec.json"
        write(spec_path, spec)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "road.xodr", "source": "work/" + ASSIGNMENT +
                               "/diagnostic-map.xodr", "sha256": sha_bytes(map_data)}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha_bytes(spec_path.read_bytes())}}
        write(directory / "diagnostic-recipe.json", recipe)
        if spec_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("diagnostic spec exceeds returned file limit")
    print("Built four bounded synthetic signal diagnostic recipes")


if __name__ == "__main__":
    main()
