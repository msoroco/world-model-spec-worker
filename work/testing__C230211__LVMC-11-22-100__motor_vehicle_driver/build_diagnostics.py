"""Generate source-bound synthetic software diagnostics for exact cases."""

import hashlib
import json
from pathlib import Path

from package_spec import AID
from pavement_protection import CASES, measure_original

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def build(case):
    spec = json.loads((ROOT / "runtime/fixtures/example.json").read_text())
    suffix = case.name
    case_id = AID + "__" + suffix
    scene = {"cell_id": "C230211", "actor": "motor_vehicle_driver",
             "person_is_driver": True, "vehicle_qualifies": True,
             "municipal_jurisdiction": True,
             "pavement_condition": "newly_laid", "pavement_rect_m": [105, 0, 115, 4],
             "pavement_id": "diagnostic-p1", "protection": case.protection,
             "route_kind": case.route, "employee_engaged": case.employee_engaged,
             "employee_pavement_id": "diagnostic-p1", "work_kind": "paving",
             "work_active": True, "protection_placed_time_s": -1,
             "barrier_rect_m": [104, 0, 105, 4],
             "barrier_perimeter_rects_m": [[104, -1, 105, 5], [115, -1, 116, 5],
                                           [105, -1, 115, 0], [105, 4, 115, 5]],
             "warning_person_id": "diagnostic-w1", "warning_person_xy": [104, 2],
             "sign_xy": [104, 2],
             "sign_text": ("highway_closed" if case.protection == "highway_closed_sign"
                           else "do_not_drive_on_pavement"),
             "vehicle_route_xy": ([[100, 2], [110, 2], [120, 2]] if case.route == "cross"
                                  else [[100, 6], [110, 6], [120, 6]])}
    for role in ("jurisdiction", "driver", "vehicle", "pavement_condition",
                 "pavement_extent", "protection_geometry", "protection_placement_time",
                 "vehicle_route", "employment", "work_activity"):
        scene[role + "_source_sha256"] = sha_bytes(("synthetic " + role).encode())
    first_trace = [json.loads(line) for line in spec["files"]["trace.jsonl"].splitlines()]
    first = first_trace[0]["frame"]
    site_sha = sha_bytes(("synthetic reviewed site " + suffix).encode())
    rows, mapping, trace = [], [], []
    for index in range(900):
        frame = first + index
        time_s = first_trace[index]["time_s"] if index < len(first_trace) else .05 + index / 20
        x = 100 if index < 100 else 110 if index < 500 else 120
        y = 2 if case.route == "cross" else 6
        if index < len(first_trace):
            x, y = first_trace[index]["position_m"][:2]
        row = {"frame": frame, "original_frame": frame, "time_s": time_s,
               "vehicle_id": "synthetic-ego", "vehicle_position_xy": [x, y],
               "protection": case.protection, "employee_engaged": case.employee_engaged,
               "protection_present": True, "warning_actor_ids": ["synthetic-warning"],
               "work_active": True, "employee_pavement_id": "diagnostic-p1",
               "reviewed_site_sha256": site_sha}
        rows.append(row)
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": time_s})
        trace.append(first_trace[index] if index < len(first_trace) else
                     {"frame": frame, "time_s": time_s,
                      "position_m": [x, y, 0],
                      "position": {"x": x, "y": y, "z": 0},
                      "heading_deg": 0, "speed_mps": 1,
                      "speed_mph": 1 / .44704})
    measured = measure_original(rows, scene, case)
    files = spec["files"]
    files["trace.jsonl"] = "\n".join(compact(row) for row in trace) + "\n"
    files["video_frames.jsonl"] = "\n".join(compact(row) for row in mapping) + "\n"
    files["pavement-packet.json"] = compact({"assignment_id": AID,
                                             "case_id": case_id,
                                             "reviewed_site_sha256": site_sha,
                                             "scene": scene, "frames": rows}) + "\n"
    files["pavement-measurement.json"] = compact(measured) + "\n"
    files["original-source-receipt.json"] = compact({
        "source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
        "case_id": case_id, "fps": 20, "frame_count": 900,
        "reviewed_site_sha256": site_sha,
        "packet_sha256": sha_bytes(files["pavement-packet.json"].encode()),
        "trace_sha256": sha_bytes(files["trace.jsonl"].encode()),
        "frame_map_sha256": sha_bytes(files["video_frames.jsonl"].encode()),
        "measurement_sha256": sha_bytes(files["pavement-measurement.json"].encode()),
        "physical_acceptance": False, "legal_verdict": None}) + "\n"
    for video in spec["videos"]:
        video["frames"] = 900
    generator_path = HERE / "diagnostics" / (suffix + "-generator.json")
    generator_path.parent.mkdir(exist_ok=True)
    generator_path.write_text(compact(spec) + "\n")
    if generator_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic generator exceeds 2 MiB")
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json",
                           "source": "runtime/fixtures/example.json",
                           "sha256": sha(ROOT / "runtime/fixtures/example.json")}],
              "generator": {"source": "work/" + AID + "/diagnostics/" + generator_path.name,
                            "sha256": sha(generator_path)}}
    recipe_path = HERE / "diagnostics" / (suffix + "-recipe.json")
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    return generator_path.stat().st_size


if __name__ == "__main__":
    for item in CASES:
        print(item.name, build(item))
