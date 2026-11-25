"""Build explicit two-case CPU diagnostic sources and public package scaffold."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
CASE_PREFIX = ASSIGNMENT + "__probe_"
SOURCE_ROOT = ROOT / "diagnostic"
EXAMPLE_ROAD = REPO / "work/training__C110919__NRS-484B-307-8c__motor_vehicle_driver/current-v2-probe_a-fixture/road.xodr"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def lines(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows))


def source_data(suffix: str) -> tuple[dict, dict]:
    case = CASE_PREFIX + suffix
    output = SOURCE_ROOT / suffix
    output.mkdir(parents=True, exist_ok=True)
    property_route = suffix == "02"
    survey = {
        "source_kind": "synthetic_native_property_survey", "assignment_id": ASSIGNMENT,
        "map_name": "synthetic_property_bypass_fixture", "property_boundary_source": "diagnostic polygon",
        "approach_signal_lens_form": "circular_red_alone",
        "approach_signal_facing_source_id": "synthetic-facing-survey",
        "approach_signal_actor_id": 601, "cross_signal_actor_id": 602,
        "approach_lane_source": "synthetic-one-way-approach",
        "cross_street_lane_source": "synthetic-one-way-cross",
        "property_id": "synthetic-parcel-1", "property_boundary_source_id": "synthetic-parcel-boundary-1",
        "property_polygon_xy_m": [[9, -2], [11, -2], [11, 2], [9, 2]],
        "cross_street_polygon_xy_m": [[19, -2], [21, -2], [21, 2], [19, 2]],
        "spawn_xyz_yaw_deg": [0, 0, 0.5, 0],
        "route_xyz_m": [[0, 0, 0.5], [10, 0, 0.5], [20, 0, 0.5]],
        "road_only_route_xyz_m": [[0, 0, 0.5], [0, 5, 0.5], [20, 5, 0.5]],
        "synthetic_diagnostic": True,
    }
    purpose = {"source_kind": "synthetic_controller_purpose_declaration",
               "assignment_id": ASSIGNMENT,
               "declaration_source_id": "synthetic-controller-plan:" + ASSIGNMENT,
               "declared_purpose": "avoid_red_signal", "synthetic_diagnostic": True}
    put(output / "property-survey.json", survey)
    put(output / "purpose-declaration.json", purpose)
    native, trace, evidence, mapping, frames, graphs = [], [], [], [], [], []
    for i in range(600):
        frame = i + 100
        time = i / 20
        x = round(min(20, i * 0.05), 5) if property_route else 0.0
        y = 0.0
        speed = 1.0 if property_route and i < 400 else 0.0
        body = [[round(x - 0.4, 5), -0.4], [round(x + 0.4, 5), -0.4],
                [round(x + 0.4, 5), 0.4], [round(x - 0.4, 5), 0.4]]
        native.append({"source_kind": "synthetic_native_fixture", "frame": i,
                       "native_frame": frame, "t_s": time, "vehicle_id": 107,
                       "x_m": x, "y_m": y, "body_vertices_xy_m": body,
                       "speed_mps": speed, "route_target_index": 0 if i < 200 else 1,
                       "zone": "diagnostic_hint_only",
                       "approach_signal_native_state": "Red", "cross_signal_native_state": "Green",
                       "approach_signal_actor_id": 601, "cross_signal_actor_id": 602,
                       "purpose_declaration": "avoid_red_signal"})
        trace.append({"frame": frame, "time_s": time,
                      "position": {"x": x, "y": y, "z": 0.5},
                      "position_m": [x, y, 0.5], "heading_deg": 0.0,
                      "speed_mps": speed, "speed_mph": speed * 2.23693629,
                      "velocity_mps": [speed, 0, 0],
                      "control": {"throttle": 0, "brake": 0, "hand_brake": False}})
        body3 = [[point[0], point[1], z] for point in body for z in (0, 1.5)]
        evidence.append({"original_frame": frame, "recording_time_s": time,
                         "replay_frame": frame, "replay_simulation_time_s": time,
                         "actor_id": 107,
                         "ego": {"body_vertices_m": body3, "position_m": [x, y, 0.5],
                                 "heading_deg": 0, "speed_mps": speed,
                                 "speed_provenance": "synthetic_native_sample",
                                 "synthetic_diagnostic": True},
                         "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                               "wetness": 0, "fog_density": 0},
                                   "road_projection": {"road_id": 1, "section_id": 0,
                                                       "lane_id": -1, "s_m": x}}})
        mapping.append({"video_frame": i, "native_frame": frame,
                        "carla_frame": frame, "time_s": time})
        path = f"capture/native/graphs/base/{frame:08d}.adapter.json"
        frames.append({"frame": frame, "simulation_time": time, "time_s": time,
                       "adapter_graph": f"graphs/base/{frame:08d}.adapter.json",
                       "synthetic_diagnostic": True})
        graphs.append({"path": path,
                       "attributes": {"frame": frame, "simulation_time_s": time,
                                      "units": "m", "observed_evidence": "synthetic_diagnostic"},
                       "nodes": [{"id": "ego", "attributes": {"sem_class": "vehicle.tesla.model3",
                                                                "carla_id": 107,
                                                                "vertex": [x, y, 0.5]}}],
                       "edges": []})
    lines(output / "property-route-native.jsonl", native)
    lines(output / "trace.jsonl", trace)
    lines(output / "capture/evidence.jsonl", evidence)
    lines(output / "video_frames.jsonl", mapping)
    (output / "road.xodr").write_text(EXAMPLE_ROAD.read_text())
    put(output / "capture/manifest.json", {"extraction_confirmed": True, "frames": 600,
         "synthetic_diagnostic": True,
         "sources": {"road.xodr": sha(output / "road.xodr"),
                     "trace.jsonl": sha(output / "trace.jsonl")}})
    put(output / "context.json", {"property_route_survey": survey,
                                   "synthetic_diagnostic": True})
    spec = {"files": {"capture/native/frames.jsonl": "".join(
                     json.dumps(row, sort_keys=True) + "\n" for row in frames),
                     "capture/recorder_info.txt": "synthetic CPU diagnostic frames only\n"},
            "graphs": graphs,
            "videos": [{"path": name + ".mkv", "frames": 600,
                        "width": 1920 if name == "overview" else 1280,
                        "height": 1080 if name == "overview" else 720,
                        "fps": 20, "color": "black"} for name in VIEWS]}
    spec_path = ROOT / f"diagnostic-{suffix}-spec.json"
    put(spec_path, spec)
    rel = output.relative_to(REPO)
    sources = []
    for name in ("property-survey.json", "purpose-declaration.json", "property-route-native.jsonl",
                 "trace.jsonl", "capture/evidence.jsonl", "video_frames.jsonl",
                 "road.xodr", "capture/manifest.json", "context.json"):
        path = output / name
        sources.append({"path": name, "source": str(rel / name), "sha256": sha(path)})
    recipe_path = ROOT / f"diagnostic-{suffix}-recipe.json"
    put(recipe_path, {"format": "worker-fixture-recipe", "sources": sources,
                      "generator": {"source": str(spec_path.relative_to(REPO)),
                                    "sha256": sha(spec_path)}})
    return {"case_id": case, "fixture_recipe": str(recipe_path.relative_to(REPO)),
            "diagnostic_spec_sha256": sha(spec_path)}


def main() -> None:
    metadata = [source_data(suffix) for suffix in ("01", "02")]
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
