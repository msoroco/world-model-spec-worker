"""Build explicit synthetic CPU fixtures for saved package compatibility only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nearest_view import REQUIRED_SOURCES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = ("nearest_view_hold", "nearest_view_continue", "nearest_view_clear",
         "active_signal_exception")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic source exceeds work size cap: " + str(path))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_case(case: str) -> dict:
    case_id = ASSIGNMENT + "__" + case
    folder = HERE / "fixtures" / case
    folder.mkdir(parents=True, exist_ok=True)
    context = {"cell_id": "C158196", "law_id": "NRS-484B-257-1",
               "proper_yield_sign": True, "through_highway": True,
               "connected_approach": True, "marked_stop_line": False,
               "near_side_crosswalk": False, "sidewalk_derived_crosswalk": False,
               "officer_controlling": False,
               "signal_controlling": case == "active_signal_exception",
               "nearest_view_station_m": 2.1, "intersection_entry_station_m": 4.5}
    frames, raw, trace, mapping, history, cameras = [], [], [], [], [], []
    for index in range(900):
        frame, time = 100 + index, 5 + index / 20
        front = 2 + index * .01
        occupied = case != "nearest_view_clear"
        body = [[front - 1, -.5], [front, -.5], [front, .5], [front - 1, .5]]
        through = [[5, -.5], [6, -.5], [6, .5], [5, .5]] if occupied else (
            [[20, -.5], [21, -.5], [21, .5], [20, .5]])
        speed = .01 if case == "nearest_view_hold" and index >= 245 else .2
        frames.append({"frame": frame, "time_s": time, "ego_front_station_m": front,
                       "ego_speed_mps": speed, "through_center_station_m": 5.5 if occupied else 20.5,
                       "view_clear": True, "through_occupied": occupied,
                       "ego_within_intersection": 250 <= index < 600})
        raw.append({"frame": frame, "time_s": time, "ego_body_xy_m": body,
                    "through_body_xy_m": through,
                    "ego_velocity_xy_mps": [speed, 0],
                    "through_center_xy_m": [5.5 if occupied else 20.5, 0],
                    "native_view_raycast": {"source": "diagnostic_raycast",
                                            "occluded": False},
                    "yield_sign_readback": True,
                    "signal_controlling": case == "active_signal_exception",
                    "officer_controlling": False})
        trace.append({"frame": frame, "time_s": time,
                      "position": {"x": front - .5, "y": 0, "z": 0},
                      "heading_deg": 0, "speed_mps": speed})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": time})
        history.append({"frame": frame, "time_s": time,
                        "ego": {"body_vertices_m": [[x, y, 0] for x, y in body]}})
        cameras.append({"frame": frame, "pixel_sha256": {name: "0" * 64 for name in VIEWS}})
    sources = {}
    for name in REQUIRED_SOURCES:
        path = folder / (name + ".json")
        if name == "signal_state_readback" and case == "active_signal_exception":
            rows = [{"frame": 100 + i, "state": "green" if i < 400 else "red",
                     "governs_ego_approach": True} for i in range(900)]
            value = {"source_kind": "original_native_signal_readback",
                     "device_kind": "traffic_control_signal",
                     "governs_ego_approach": True,
                     "observed_frame_ids": [100 + i for i in range(900)],
                     "observed_signal_states": rows,
                     "diagnostic_fixture": True}
        else:
            value = {"diagnostic_fixture": True, "source_name": name,
                     "case_id": case_id}
        _write(path, value)
        sources[name] = {"path": path.name, "sha256": _sha(path)}
    packet = {"case_id": case_id, "context": context,
              "site_source_hashes": {"diagnostic": "0" * 64},
              "sources": sources, "frames": frames, "raw_frames": raw,
              "diagnostic_fixture": True}
    _write(folder / "nearest-view-original.json", packet)
    _write(folder / "camera-frame-map.json", cameras)
    _write(folder / "camera-sources.json", {
        "format": "c158196-diagnostic-four-camera-sources-v1",
        "case_id": case_id,
        "frame_map_sha256": _sha(folder / "camera-frame-map.json"),
        "sources": {name: {"path": name + ".mkv", "frame_count": 900} for name in VIEWS},
        "diagnostic": True})
    for name, rows in (("trace.jsonl", trace), ("video_frames.jsonl", mapping),
                       ("interaction_history.jsonl", history)):
        path = folder / name
        path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("diagnostic source exceeds work size cap: " + str(path))
    _write(folder / "control_context.json", {
        "source_kind": "diagnostic_fixture_control_context",
        "intersection_polygon_xy_m": [[4.5, -2], [8, -2], [8, 2], [4.5, 2]]})
    _write(folder / "fixture-provenance.json", {
        "diagnostic_fixture": True, "physical_acceptance_claimed": False})
    _write(folder / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    videos = [{"path": name + ".mkv", "frames": 900,
               "width": 1920 if name == "overview" else 1280,
               "height": 1080 if name == "overview" else 720,
               "fps": 20, "color": "black"} for name in VIEWS]
    specification = HERE / ("diagnostic-" + case + "-spec.json")
    _write(specification, {"files": {}, "graphs": [], "videos": videos})
    inventory = [{"path": path.name,
                  "source": str(path.relative_to(ROOT)), "sha256": _sha(path)}
                 for path in sorted(folder.iterdir()) if path.is_file()]
    recipe = HERE / ("diagnostic-" + case + "-recipe.json")
    _write(recipe, {"format": "worker-fixture-recipe", "sources": inventory,
                    "generator": {"source": str(specification.relative_to(ROOT)),
                                  "sha256": _sha(specification)}})
    return {"case_id": case_id, "files": len(inventory), "recipe": recipe.name}


if __name__ == "__main__":
    for variant in CASES:
        print(build_case(variant))
