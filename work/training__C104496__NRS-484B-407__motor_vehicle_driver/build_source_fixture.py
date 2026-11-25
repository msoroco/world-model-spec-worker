"""Build C104496-only textual Core/video diagnostics from authored turn requests.

These are synthetic source shapes. They never assert a realized reversal,
500-foot body visibility, recognition or legal result.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RATE = 20
FRAMES = 700
CASES = (("probe_01", "crest"), ("probe_02", "crest"), ("probe_03", "curve"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n")


def dump(value) -> str:
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def bbox(center, heading):
    x, y, z = center
    direction = (math.cos(heading), math.sin(heading))
    normal = (-direction[1], direction[0])
    return [[round(x + length * direction[0] + width * normal[0], 5),
             round(y + length * direction[1] + width * normal[1], 5),
             round(z + height, 5)]
            for length in (-2.25, 2.25)
            for width in (-0.9, 0.9)
            for height in (-0.5, 1.0)]


def build_case(suffix: str, branch: str):
    original = HERE / "native" / branch / "drafts" / suffix / "primary"
    out = HERE / "source-fixture" / suffix
    scope = json.loads((original / "config.json").read_text())
    requests = [json.loads(line) for line in
                (original / "requested-tracks.jsonl").read_text().splitlines()]
    if len(requests) != FRAMES or scope["case_id"] != HERE.name + "__" + suffix:
        raise ValueError("exact authored 700-frame request missing")
    road = original / (branch + ".xodr")
    put(out / "road.xodr", road.read_text())
    trace = []
    evidence = []
    frame_map = []
    graph_frames = []
    graphs = []
    turn_history = []
    analytic_sight = []
    raw = json.loads((HERE / "native" / branch / "synthetic" / suffix /
                      "primary" / "raw.json").read_text())
    if len(raw["rows"]) != FRAMES or raw["case_id"] != scope["case_id"]:
        raise ValueError("exact saved analytic ray source missing")
    for index, request in enumerate(requests):
        frame = 1000 + index
        time_s = index / RATE
        center = request["requested_ego_xyz_m"]
        heading = request["requested_heading_rad"]
        other = request["requested_other_vehicle_xyz_m"]
        speed = request["requested_speed_mps"]
        body = bbox(center, heading)
        other_body = bbox(other, 0.0)
        sight = raw["rows"][index]
        if sight["frame"] != index or sight["requested_ego_xyz_m"] != center:
            raise ValueError("authored request and saved ray source differ")
        analytic_sight.append({"frame": frame, "time_s": time_s,
                               "observer_stations_m": sight.get("observer_stations_m",
                                  sight.get("observer_road_stations_m")),
                               "analytic_road_above_ray_m": sight["analytic_road_above_ray_m"],
                               "source_kind": "synthetic_authored_geometry",
                               "original_body_visibility_verified": False})
        turn_history.append({"frame": frame, "time_s": time_s,
                             "body_vertices_m": body,
                             "heading_deg": round(math.degrees(heading), 5),
                             "requested_motion_phase": request["requested_motion_phase"],
                             "synthetic_diagnostic": True})
        velocity = [round(speed * math.cos(heading), 5),
                    round(speed * math.sin(heading), 5), 0]
        trace.append({"frame": frame, "time_s": time_s,
                      "position": dict(zip(("x", "y", "z"), center)),
                      "position_m": center, "heading_deg": round(math.degrees(heading), 5),
                      "speed_mps": speed, "speed_mph": round(speed * 2.2369362921, 5),
                      "velocity_mps": velocity,
                      "control": {"throttle": 0.2, "brake": 0, "hand_brake": False}})
        evidence.append({"original_frame": frame, "replay_frame": frame,
                         "actor_id": 107, "recording_time_s": time_s,
                         "replay_simulation_time_s": time_s,
                         "ego": {"position_m": center,
                                 "heading_deg": round(math.degrees(heading), 5),
                                 "speed_mps": speed,
                                 "speed_provenance": "synthetic_native_sample",
                                 "body_vertices_m": body},
                         "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                               "wetness": 0, "fog_density": 0},
                                   "road_projection": {"road_id": 407, "section_id": 0,
                                                       "lane_id": -1, "s_m": center[0]}}})
        frame_map.append({"video_frame": index, "carla_frame": frame,
                          "native_frame": frame, "time_s": time_s})
        graph_path = f"capture/native/graphs/base/{frame:08d}.adapter.json"
        graph_frames.append({"frame": frame, "simulation_time": time_s,
                             "time_s": time_s,
                             "base": f"graphs/base/{frame:08d}.adapter.json",
                             "abstract": f"graphs/abstract/{frame:08d}.pkl",
                             "adapter_graph": f"graphs/base/{frame:08d}.adapter.json",
                             "synthetic_diagnostic": True})
        graphs.append({"path": graph_path,
                       "attributes": {"frame": frame,
                                      "simulation_time_s": time_s,
                                      "synthetic_diagnostic": True},
                       "nodes": [
                           {"id": "ego", "attributes": {"sem_class": "ego",
                                 "entity_id": 107, "vertex": center,
                                 "forward": [round(math.cos(heading), 5),
                                             round(math.sin(heading), 5), 0],
                                 "threedbbox": body}},
                           {"id": "approach", "attributes": {"sem_class": "vehicle",
                                 "entity_id": 108, "vertex": other,
                                 "forward": [1, 0, 0], "threedbbox": other_body}}],
                       "edges": []})
    for name, rows in (("trace.jsonl", trace),
                       ("capture/evidence.jsonl", evidence),
                       ("video_frames.jsonl", frame_map),
                       ("turn_history.jsonl", turn_history),
                       ("analytic_sight.jsonl", analytic_sight),
                       ("capture/native/frames.jsonl", graph_frames)):
        put(out / name, "\n".join(dump(row) for row in rows))
    put(out / "curve_context.json", dump({"case_id": scope["case_id"],
        "road_kind": branch, "authored_road_sha256": sha(out / "road.xodr"),
        "synthetic_diagnostic": True, "original_native_verified": False}))
    manifest = {"acquisition": "synthetic_diagnostic",
                "frames": FRAMES, "extraction_confirmed": True,
                "observation_contract_version": 1,
                "required_observations": (["kin.position", "st.grade", "st.curvature"]
                                          if branch == "crest" else ["kin.position"]),
                "sources": {"road.xodr": sha(out / "road.xodr"),
                            "trace.jsonl": sha(out / "trace.jsonl")},
                "synthetic_diagnostic": True}
    put(out / "capture/manifest.json", dump(manifest))
    put(out / "capture/recorder_info.txt",
        "Synthetic C104496 textual diagnostic; no CARLA recorder or original media\n"
        "Create 107: " + scope["ego_blueprint"] + " (synthetic fixture identity)")
    put(out / "acquisition-provenance.json",
        dump({"provenance_kind": "synthetic_local_diagnostic",
              "diagnostic_fixture": True, "native_executed": False,
              "requested_case_id": scope["case_id"],
              "requested_road_sha256": sha(road)}))
    put(out / "case-scope.json",
        dump({"format": "c104496-synthetic-source-scope-v1",
              "case_id": scope["case_id"],
              "law_id": "NRS-484B-407",
              "source_text": scope["source_text"],
              "grade_height_m": scope["grade_height_m"],
              "road_kind": branch,
              "original_visibility_verified": False,
              "original_reversal_verified": False, "legal_verdict": None}))
    videos = [{"path": name + ".mkv", "frames": FRAMES,
               "width": 1920 if name == "overview" else 1280,
               "height": 1080 if name == "overview" else 720,
               "fps": RATE, "color": "black"}
              for name in ("overview", "approach", "reference_corner",
                           "driver_reference")]
    diagnostic = {"files": {}, "graphs": graphs, "videos": videos}
    diagnostic_path = out / "diagnostic.json"
    put(diagnostic_path, dump(diagnostic))
    source_names = ("road.xodr", "trace.jsonl", "capture/evidence.jsonl",
                    "video_frames.jsonl", "turn_history.jsonl",
                    "analytic_sight.jsonl", "curve_context.json",
                    "capture/native/frames.jsonl",
                    "capture/manifest.json", "capture/recorder_info.txt",
                    "acquisition-provenance.json", "case-scope.json")
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": name,
                           "source": str((out / name).relative_to(ROOT)),
                           "sha256": sha(out / name)} for name in source_names],
              "generator": {"source": str(diagnostic_path.relative_to(ROOT)),
                            "sha256": sha(diagnostic_path)}}
    recipe_path = out / "recipe.json"
    put(recipe_path, json.dumps(recipe, indent=2))
    if any(path.stat().st_size > 2 * 1024 * 1024 for path in out.rglob("*",)
           if path.is_file()):
        raise ValueError("returned source fixture file exceeds 2 MiB")
    return {"case_id": scope["case_id"], "graph_frames": len(graphs),
            "diagnostic_bytes": diagnostic_path.stat().st_size,
            "recipe_sha256": sha(recipe_path)}


def main():
    cases = [build_case(suffix, branch) for suffix, branch in CASES]
    print(json.dumps({"cases": cases, "physical_original_proven": False}))


if __name__ == "__main__":
    main()
