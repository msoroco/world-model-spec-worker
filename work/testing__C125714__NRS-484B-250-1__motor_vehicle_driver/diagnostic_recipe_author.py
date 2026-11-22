"""Author an exact-case textual fixture; all content is synthetic CPU data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIANTS = (("precedence", 4, 2), ("advance", 4, 2), ("other_later", 2, 4),
            ("opposite_straight", 4, 2), ("opposite_intends_left", 4, 2),
            ("opposite_makes_left", 4, 3), ("wide_same_crossing", 4, 2))


def encoded(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n"


def body(x, y):
    return [[x-.2, y-.2], [x+.2, y-.2], [x+.2, y+.2], [x-.2, y+.2]]


def build_variant(suffix, ego_entry, other_entry):
    folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
    scene = json.loads((folder / "scene.json").read_text())
    crossing = scene["crossing"]
    context = {
        "diagnostic_only": True, "ego_actor_id": 11, "other_actor_id": 22,
        "crossing": crossing,
        "law_context": {
            "map_source": crossing["map_source_sha256"],
            "ego_highway": scene["ego_highway"], "other_highway": scene["other_highway"],
            "public_access_source": "synthetic CPU fixture only",
            "device_inventory_source": "synthetic CPU fixture only",
            "driver_scope_source": "synthetic CPU fixture only",
            "public_access": True, "human_driver": True, "devices": [],
            "approach_relation": scene["approach_relation"],
            "left_turn_intent": scene["left_turn_intent"],
            "left_turn_realized": scene["left_turn_realized"]}}
    files = {"intersection-context.json": encoded(context)}
    for name, actor, entry, cleared in (("ego", 11, ego_entry, 6),
                                        ("other", 22, other_entry, 6)):
        rows = []
        for frame in range(9):
            coordinate = -10 if frame < entry else (0 if frame < cleared else 10)
            if suffix == "wide_same_crossing" and name == "ego":
                x, y = -coordinate, 5.75
            elif suffix == "wide_same_crossing":
                x, y = 0, (-10 if frame < entry else (5.75 if frame < cleared else 10))
            elif name == "ego":
                x, y = coordinate, -5.75
            elif suffix == "opposite_makes_left":
                x, y = ((10, 5.75), (8, 5.75), (4, 5.75),
                        (-.066, 4.066), (-1.75, 0), (-1.75, -5),
                        (-1.75, -10), (-1.75, -13), (-1.75, -15))[frame]
            elif scene["approach_relation"] == "opposite":
                x, y = -coordinate, 5.75
            else:
                x, y = 0, coordinate
            rows.append(encoded({"frame": frame, "time_s": frame/20,
                                 "actor_id": actor, "body_vertices_xy_m": body(x, y)}))
        files[f"{name}-body-history.jsonl"] = "".join(rows)
    acquired = {name: {"kind": "original_native",
                       "sha256": hashlib.sha256(files[name].encode()).hexdigest()}
                for name in ("intersection-context.json", "ego-body-history.jsonl",
                             "other-body-history.jsonl")}
    files["acquisition.json"] = encoded(acquired)
    files["acquisition-provenance.json"] = encoded(
        {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    trace_rows = []
    for frame in range(9):
        x = -10 if frame < ego_entry else (0 if frame < 6 else 10)
        y = -5.75
        heading = 0
        if suffix == "wide_same_crossing":
            x, y, heading = -x, 5.75, 180
        trace_rows.append(encoded({"frame": frame, "time_s": frame/20,
                                   "position": {"x": x, "y": y, "z": 0},
                                   "position_m": [x, y, 0], "heading_deg": heading,
                                   "speed_mps": 0, "speed_mph": 0,
                                   "velocity_mps": [0, 0, 0], "control": {}}))
    files["trace.jsonl"] = "".join(trace_rows)
    files["video_frames.jsonl"] = "".join(encoded(
        {"video_frame": frame, "carla_frame": frame, "native_frame": frame,
         "time_s": frame/20}) for frame in range(9))
    observations = [{"frame": frame, "time_s": frame/20, "participants": [],
                     "map_context": {"declared_public_way_road_ids": []}}
                    for frame in range(9)]
    events = []
    frames = []
    graphs = []
    for frame in range(9):
        trace = json.loads(trace_rows[frame])
        original_body = json.loads(files["ego-body-history.jsonl"].splitlines()[frame])
        vertices = [[x, y, z] for x, y in original_body["body_vertices_xy_m"]
                    for z in (0, 1.5)]
        events.append({"original_frame": frame, "replay_frame": frame,
                       "actor_id": 11, "recording_time_s": frame/20,
                       "replay_simulation_time_s": frame/20,
                       "world": {"weather": {}},
                       "ego": {"position_m": trace["position_m"],
                               "heading_deg": trace["heading_deg"],
                               "speed_mps": 0, "body_vertices_m": vertices,
                               "speed_provenance": "synthetic_native_sample"},
                       "original_observations": observations[frame]})
        frames.append({"frame": frame, "simulation_time": frame/20,
                       "adapter_graph": f"graphs/base/{frame:08d}.adapter.json"})
        graphs.append({"path": f"capture/native/graphs/base/{frame:08d}.adapter.json",
                       "attributes": {"frame": frame, "time_s": frame/20,
                                      "observed_evidence": observations[frame]},
                       "nodes": [], "edges": []})
    files["capture/evidence.jsonl"] = "".join(encoded(row) for row in events)
    files["capture/native/frames.jsonl"] = "".join(encoded(row) for row in frames)
    files["capture/recorder_info.txt"] = "Create 11: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n"
    map_bytes = (ROOT / "candidate-map.xodr").read_bytes()
    files["capture/manifest.json"] = encoded({
        "status": "draft", "acquisition": "original_live_run",
        "case_id": scene["case_id"], "frames": 9,
        "extraction_confirmed": True, "complete_driving_lanes": False,
        "sources": {"road.xodr": hashlib.sha256(map_bytes).hexdigest(),
                    "trace.jsonl": hashlib.sha256(files["trace.jsonl"].encode()).hexdigest()}})
    videos = [{"path": name+".mkv", "frames": 9, "width": width,
               "height": height, "fps": 20, "color": "black"}
              for name, width, height in (("overview", 1920, 1080),
                                          ("approach", 1280, 720),
                                          ("reference_corner", 1280, 720),
                                          ("driver_reference", 1280, 720))]
    spec = {"files": files, "graphs": graphs, "videos": videos}
    path = folder / "diagnostic.json"
    path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    source = str(path.relative_to(ROOT.parent.parent))
    map_source = ROOT / "candidate-map.xodr"
    recipe = {"format": "worker-fixture-recipe", "sources": [{
                  "path": "road.xodr", "source": str(map_source.relative_to(ROOT.parent.parent)),
                  "sha256": hashlib.sha256(map_source.read_bytes()).hexdigest()}],
              "generator": {"source": source, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
    (folder / "diagnostic-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")


def build():
    for suffix, ego_entry, other_entry in VARIANTS:
        build_variant(suffix, ego_entry, other_entry)


if __name__ == "__main__":
    build()
