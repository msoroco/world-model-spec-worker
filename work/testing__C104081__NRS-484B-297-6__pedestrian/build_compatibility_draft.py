"""Build source-shaped, explicitly diagnostic compatibility inputs for five cases."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PRIVATE = REPO / ".runtime-work" / "c104081-compat-media"
CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
FRAMES = 900


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def _lines(values) -> str:
    return "".join(_text(value) for value in values)


def _world(x: float, y: float) -> list[float]:
    return [round(100 - y, 6), round(200 + x, 6)]


def _rect(x0, x1, y0, y1):
    return [_world(x, y) for x, y in ((x0, y0), (x0, y1), (x1, y1), (x1, y0))]


def _media_hashes():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, (width, height) in CAMERAS.items():
        path = PRIVATE / (name + ".mkv")
        if not path.is_file():
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-n", "-f", "lavfi", "-i",
                            f"color=c=black:s={width}x{height}:r=20", "-frames:v", str(FRAMES),
                            "-an", "-c:v", "ffv1", "-threads", "1", "-fflags", "+bitexact",
                            "-flags:v", "+bitexact", str(path)], check=True, timeout=180)
        result[name] = _sha(path.read_bytes())
    return result


def _points(params):
    end = float(params["sidewalk_end_m"])
    side = 1 if params["area_blocked"] else 3
    points = [(10, 5), (17, 5), (18, side), (25, side), (end + 2, side),
              (end + 3, 5), (50, 5)]
    if params["direction"] == -1:
        points.reverse()
    return points


def _position(points, index):
    segment = min(5, index * 6 // FRAMES)
    start = segment * FRAMES // 6
    stop = (segment + 1) * FRAMES // 6
    fraction = (index - start) / max(1, stop - start)
    a, b = points[segment], points[segment + 1]
    return (a[0] + (b[0] - a[0]) * fraction,
            a[1] + (b[1] - a[1]) * fraction)


def _case_spec(case_id, params, media_hashes, road_text):
    end = float(params["sidewalk_end_m"])
    blocked = params["area_blocked"]
    points = _points(params)
    survey = {"source_kind": "synthetic_fixture", "cell_id": "C104081",
              "layout": "hill_crest", "map_id": "diagnostic-only",
              "local_to_world": {"x": 100.0, "y": 200.0, "yaw_degrees": 90.0},
              "surface_bounds_local_m": {
                  "sidewalk": [0, 60, 4, 6], "intervening_area": [0, 60, 2, 4],
                  "designated_bicycle_lane": [0, 60, 0, 2],
                  "immediately_adjacent_highway": [0, 60, -3, 4]},
              "original_sidewalk_direction": params["direction"],
              "observed_missing_sidewalk_intervals_local_m": [[20, end]]}
    source = {"site-survey.json": _text(survey)}
    mapping, pedestrians, obstructions, traffic, evidence, trace, graph_rows, graphs = ([] for _ in range(8))
    for index in range(FRAMES):
        frame = 500 + index
        when = round(1.0 + index * .05, 7)
        x, y = _position(points, index)
        body = [_world(x + dx, y + dy) for dx, dy in
                ((-.1, -.1), (-.1, .1), (.1, .1), (.1, -.1))]
        mapping.append({"carla_frame": frame, "video_frame": index, "time_s": when})
        pedestrians.append({"frame": frame, "time_s": when,
                            "body_vertices_world_m": body})
        obstructions.append({"frame": frame, "time_s": when,
                             "intervening_barrier_present": blocked,
                             "sidewalk_obstruction_end_local_m": end,
                             "sidewalk_obstruction_kind": params["obstruction_kind"],
                             "sidewalk_obstruction_vertices_world_m": _rect(20, end, 4, 6),
                             "intervening_barrier_vertices_world_m": _rect(20, end, 2, 4) if blocked else None})
        traffic.append({"frame": frame, "time_s": when,
                        "nearest_traffic_distance_m": 20.0})
        observed = {"frame": frame, "time_s": when, "participants": [],
                    "map_context": {"diagnostic_fixture": True}}
        evidence.append({"original_frame": frame, "recording_time_s": when,
                         "replay_frame": frame, "replay_simulation_time_s": when,
                         "original_observations": observed,
                         "world": {"weather": {}}, "ego": {"position_m": [x, y, 0],
                                                              "speed_mps": 1.4}, "actor_id": 7})
        trace.append({"frame": frame, "time_s": when,
                      "position_m": [x, y, 0], "speed_mps": 1.4,
                      "heading_deg": 0 if params["direction"] == 1 else 180})
        graph_path = f"graphs/base/{frame:08d}.adapter.json"
        graph_rows.append({"frame": frame, "simulation_time": when,
                           "adapter_graph": graph_path})
        graphs.append({"path": "capture/native/" + graph_path,
                       "attributes": {"frame": frame, "time_s": when,
                                      "observed_evidence": observed},
                       "nodes": [], "edges": []})
    for name, rows in (("video_frames.jsonl", mapping),
                       ("pedestrian_history.jsonl", pedestrians),
                       ("obstruction_history.jsonl", obstructions),
                       ("traffic_history.jsonl", traffic),
                       ("capture/evidence.jsonl", evidence),
                       ("trace.jsonl", trace),
                       ("capture/native/frames.jsonl", graph_rows)):
        source[name] = _lines(rows)
    source["capture/recorder_info.txt"] = "Create 7: walker.pedestrian.0001 (diagnostic) at (0, 0, 0)\n"
    packet_files = {name: {"path": name, "sha256": _sha(source[name].encode())}
                    for name in ("site-survey.json", "video_frames.jsonl", "pedestrian_history.jsonl",
                                 "obstruction_history.jsonl", "traffic_history.jsonl")}
    packet = {"case_id": case_id, "source_kind": "synthetic_fixture",
              "capture_context": {"pedestrian_blueprint": "walker.pedestrian.0001",
                                  "camera_profile_sha256": "a" * 64,
                                  "traffic_plan_sha256": "b" * 64},
              "files": packet_files,
              "camera_media": {name: {"path": name + ".mkv", "sha256": digest,
                                        "frame_count": FRAMES, "fps": 20}
                               for name, digest in media_hashes.items()}}
    source["source-packet.json"] = _text(packet)
    source["pedestrian-packet.json"] = source["source-packet.json"]
    source["capture/manifest.json"] = _text({
        "acquisition": "synthetic_fixture", "case_id": case_id,
        "diagnostic_fixture": True, "extraction_confirmed": True,
        "frames": FRAMES,
        "sources": {"road.xodr": _sha(road_text.encode()),
                    "trace.jsonl": _sha(source["trace.jsonl"].encode())}})
    return {"files": source, "graphs": graphs,
            "videos": [{"path": name + ".mkv", "frames": FRAMES,
                        "width": size[0], "height": size[1], "fps": 20, "color": "black"}
                       for name, size in CAMERAS.items()]}


def build():
    media = _media_hashes()
    road = json.loads((REPO / "runtime/fixtures/example.json").read_text())["files"]["road.xodr"]
    road_path = ROOT / "diagnostic-road.xodr"
    road_path.write_text(road.rstrip() + "\n")
    road = road_path.read_text()
    manifest_path = ROOT / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["format"] = "worker-execution-manifest"
    manifest["runtime_manifest_sha256"] = _sha((REPO / "runtime/SOURCE-MANIFEST.json").read_bytes())
    manifest["status"] = "draft_diagnostic_only"
    plan = json.loads((ROOT / "case-plan.json").read_text())
    for item, entry in zip(plan["cases"], manifest["cases"]):
        case_id = item["case_id"]
        if entry["case_id"] != case_id:
            raise ValueError("exact case ordering changed")
        suffix = case_id.removeprefix(ROOT.name + "__")
        spec = _case_spec(case_id, item["construction_parameters"], media, road)
        spec_path = ROOT / ("diagnostic-" + suffix + ".json")
        spec_path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
        if spec_path.stat().st_size > 2 * 1048576:
            raise ValueError("diagnostic specification exceeds work file cap")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "road.xodr", "source": str(road_path.relative_to(REPO)),
                               "sha256": _sha(road_path.read_bytes())}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": _sha(spec_path.read_bytes())}}
        recipe_path = ROOT / ("fixture-recipe-" + suffix + ".json")
        recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
        entry["kind"] = "delivery"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("built", len(manifest["cases"]), "source-shaped diagnostic recipes")


if __name__ == "__main__":
    build()
