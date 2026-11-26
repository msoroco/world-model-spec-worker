"""Synthetic four-case converter fixtures; never original site evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cycle_lane_intersection import ASSIGNMENT
from cycle_lane_site import _polygon
from cycle_lane_original import _intersects

ROOT = Path(__file__).resolve().parent


def compact(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def lines(rows):
    return "".join(compact(row) + "\n" for row in rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(compact(value) + "\n", encoding="utf-8")


def build(case):
    suffix = case["case_id"].removeprefix(ASSIGNMENT + "__")
    case_id = case["case_id"]
    lane = _polygon([[0, 3], [40, 3], [40, 5], [0, 5]])
    intersection = _polygon([[20, 0], [30, 0], [30, 10], [20, 10]])
    site = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_cpu_fixture",
            "diagnostic_fixture": True, "map_id": "C230223 synthetic converter geometry",
            "intersection_id": "synthetic-crossroad", "cycle_lane_id": "synthetic-cycle-facility",
            "cycle_lane_designated_for": "bicycle", "designation_authority": "synthetic-only",
            "intersection_is_public_highway_junction": True, "not_alley_junction": True,
            "intersection_polygon": [list(point) for point in intersection],
            "cycle_lane_polygon": [list(point) for point in lane],
            "route_candidates": {
                "cycle_lane_through_intersection": [[0, 4], [225, 4]],
                "cycle_lane_before_intersection_only": [[0, 4], [15, 4], [15, 8], [225, 8]],
                "ordinary_lane_through_intersection": [[0, 8], [225, 8]],
                "cycle_lane_exception_unresolved": [[0, 4], [225, 4]]}}
    exception = {"source_kind": "synthetic_cpu_fixture", "diagnostic_fixture": True,
                 "law_id": "NRS-484B-270-3", "status": case["requested_subsection_3_exception_status"],
                 "authoritative_clause": "synthetic test clause; not legal authority"}
    history = []
    trace = []
    evidence = []
    frames = []
    graphs = []
    native_index = []
    for i in range(900):
        x = i * .25
        y = (8 if suffix == "ordinary_lane_through_intersection" or
             (suffix == "cycle_lane_before_intersection_only" and x >= 15) else 4)
        body = _polygon([[x-.1, y-.1], [x+.1, y-.1],
                         [x+.1, y+.1], [x-.1, y+.1]])
        within_j = _intersects(body, intersection)
        within_l = _intersects(body, lane)
        history.append({"frame": i, "time_s": i/20, "ego_actor_id": 11,
                        "ego_body_polygon": [list(point) for point in body],
                        "ego_body_in_intersection": within_j,
                        "ego_body_in_designated_cycle_lane": within_l})
        trace.append({"frame": i, "time_s": i/20,
                      "position_m": [x, y, 0],
                      "position": {"x": x, "y": y, "z": 0},
                      "speed_mps": 5.0, "speed_mph": 5.0/.44704,
                      "velocity_mps": [5.0, 0.0, 0.0], "heading_deg": 0,
                      "control": {}})
        frames.append({"video_frame": i, "carla_frame": i,
                       "native_frame": i, "time_s": i/20})
        observation = {"frame": i, "time_s": i/20,
                       "participants": [], "map_context": {"declared_public_way_road_ids": []}}
        evidence.append({"original_frame": i, "replay_frame": i,
                         "actor_id": 11, "recording_time_s": i/20,
                         "replay_simulation_time_s": i/20,
                         "world": {"weather": {}},
                         "ego": {"position_m": [x, y, 0], "heading_deg": 0,
                                 "speed_mps": 5.0,
                                 "speed_provenance": "synthetic_native_sample",
                                 "body_vertices_m": [[vx, vy, z] for vx, vy in body for z in (0, 1.5)]},
                         "original_observations": observation})
        graph_rel = f"graphs/base/{i:08d}.adapter.json"
        graphs.append({"path": "capture/native/" + graph_rel,
                       "attributes": {"frame": i, "time_s": i/20,
                                      "observed_evidence": observation},
                       "nodes": [], "edges": []})
        native_index.append({"frame": i, "simulation_time": i/20,
                             "adapter_graph": graph_rel})
    source_map = sha(ROOT / "diagnostic-map.xodr")
    file_map = {"site-source.json": compact(site) + "\n",
                "subsection_3-source.json": compact(exception) + "\n",
                "history.json": compact(history) + "\n",
                "trace.jsonl": lines(trace),
                "video_frames.jsonl": lines(frames),
                "capture/evidence.jsonl": lines(evidence),
                "capture/native/frames.jsonl": lines(native_index),
                "capture/recorder_info.txt": "Create 11: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n",
                "capture/manifest.json": compact({"status": "draft",
                    "acquisition": "synthetic_cpu_fixture", "case_id": case_id,
                    "frames": 900, "extraction_confirmed": True,
                    "complete_driving_lanes": False,
                    "sources": {"road.xodr": source_map,
                                "trace.jsonl": hashlib.sha256(lines(trace).encode()).hexdigest()}}) + "\n",
                "acquisition-provenance.json": compact({"provenance_kind": "synthetic_fixture",
                                                          "diagnostic_fixture": True}) + "\n"}
    videos = [{"path": name + ".mkv", "frames": 900,
               "width": 1920 if name == "overview" else 1280,
               "height": 1080 if name == "overview" else 720,
               "fps": 20, "color": "black"}
              for name in ("overview", "approach", "reference_corner", "driver_reference")]
    relative = f"cases/{suffix}/diagnostic-spec.json"
    write(ROOT / relative, {"files": file_map, "graphs": graphs, "videos": videos})
    recipe_relative = f"cases/{suffix}/diagnostic-recipe.json"
    source = ROOT / "diagnostic-map.xodr"
    write(ROOT / recipe_relative, {"format": "worker-fixture-recipe",
          "sources": [{"path": "road.xodr", "source": str(source.relative_to(ROOT.parents[1])),
                       "sha256": source_map}],
          "generator": {"source": str((ROOT / relative).relative_to(ROOT.parents[1])),
                        "sha256": sha(ROOT / relative)}})
    return relative, (ROOT / relative).stat().st_size


if __name__ == "__main__":
    plan = json.loads((ROOT / "case-plan.json").read_text())
    for case in plan["cases"]:
        print(case["case_id"].split("__")[-1], *build(case))
