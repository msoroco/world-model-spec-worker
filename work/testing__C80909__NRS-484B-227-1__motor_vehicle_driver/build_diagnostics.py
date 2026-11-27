"""Create explicit source-bound textual compatibility recipes for exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n"


def rows(values):
    return "".join(encode(value) for value in values)


def sha_bytes(content):
    return hashlib.sha256(content.encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        folder = HERE / "cases" / suffix
        construction = json.loads((HERE / entry["construction"]).read_text())
        source = {item["path"]: item["content"] for item in construction["files"]}
        scene = json.loads(source["scene.json"])
        reviewed = json.loads(source["reviewed-median-context.json"])
        context = dict(reviewed["context"])
        context.update(ego_actor_id=7, observed_vehicle_actor_id=8,
                       divider_actor_ids=list(range(31, 31 + len(reviewed["divider_props"]))),
                       reviewed_context_sha256=sha_bytes(source["reviewed-median-context.json"]))
        props = [{"actor_id": 31 + i, "blueprint_id": prop["blueprint_id"],
                  "body_vertices_xy_m": [[bounds[0], bounds[1]], [bounds[2], bounds[1]],
                                         [bounds[2], bounds[3]], [bounds[0], bounds[3]]]}
                 for i, prop in enumerate(reviewed["divider_props"])
                 for bounds in [prop["bounds_xy_m"]]]
        route = scene["route_xy_m"]
        n = len(route)
        body = []
        for i, (x, y) in enumerate(route):
            heading = 0 if suffix in ("closed_divider", "right_roadway_no_turn") else round(180 * i / (n - 1), 3)
            if suffix == "opening_multiple":
                heading = [0, 0, 0, 0, 0, 0, 90, 135, 160, 180][i]
            velocity = [1, 0] if i == 0 else [x-route[i-1][0], y-route[i-1][1]]
            if suffix == "opening_multiple" and i == 5:
                velocity = [-1, 0]
            half_y = 2.25 if suffix == "closed_divider" else .2
            body.append({"frame": i, "time_s": i/20, "actor_id": 7,
                         "road_id": scene["destination_road_id"] if i == n-1 else scene["source_road_id"],
                         "body_vertices_xy_m": [[x-.2,y-half_y],[x+.2,y-half_y],
                                                [x+.2,y+half_y],[x-.2,y+half_y]],
                         "heading_deg": heading, "velocity_xy_mps": velocity})
        trace = [{"frame": r["frame"], "time_s": r["time_s"],
                  "position": {"x": route[i][0], "y": route[i][1], "z": 0},
                  "position_m": [route[i][0], route[i][1], 0],
                  "heading_deg": r["heading_deg"],
                  "speed_mps": (r["velocity_xy_mps"][0]**2+r["velocity_xy_mps"][1]**2)**.5,
                  "speed_mph": (r["velocity_xy_mps"][0]**2+r["velocity_xy_mps"][1]**2)**.5/.44704,
                  "velocity_mps": [*r["velocity_xy_mps"], 0], "control": {}}
                 for i,r in enumerate(body)]
        observations = [{"frame": i, "time_s": i/20, "participants": [],
                         "map_context": {"declared_public_way_road_ids": []}} for i in range(n)]
        events = [{"original_frame": i, "replay_frame": i, "actor_id": 7,
                   "recording_time_s": i/20, "replay_simulation_time_s": i/20,
                   "world": {"weather": {}},
                   "ego": {"position_m": [route[i][0], route[i][1], 0],
                           "heading_deg": trace[i]["heading_deg"],
                           "speed_mps": trace[i]["speed_mps"],
                           "body_vertices_m": [[x,y,z] for x,y in body[i]["body_vertices_xy_m"] for z in (0,1.5)],
                           "speed_provenance": "synthetic_native_sample"},
                   "original_observations": observations[i]}
                  for i in range(n)]
        frames = [{"frame": i, "simulation_time": i/20, "adapter_graph": f"graphs/base/{i:08d}.adapter.json"}
                  for i in range(n)]
        graph_specs = [{"path": f"capture/native/graphs/base/{i:08d}.adapter.json",
                        "attributes": {"frame": i, "time_s": i/20,
                                       "observed_evidence": observations[i]},
                        "nodes": [], "edges": []} for i in range(n)]
        files = {
            "median-context.json": encode(context),
            "divider-geometry.json": encode({"actors": props}),
            "ego-body-history.jsonl": rows(body),
            "observed-vehicle-history.jsonl": rows([
                {"frame": i, "time_s": i/20, "actor_id": 8,
                 "body_vertices_xy_m": [[11.8,5.55],[12.2,5.55],[12.2,5.95],[11.8,5.95]],
                 "heading_deg":180, "velocity_xy_mps":[0,0]}
                for i in range(n)]),
            "controller-history.jsonl": rows([{"frame": r["frame"], "time_s": r["time_s"],
                                                 "ego_actor_id": 7, "next_tick_request": {}} for r in body]),
            "video_frames.jsonl": rows([{"carla_frame": i, "video_frame": i, "time_s": i/20} for i in range(n)]),
            "trace.jsonl": rows(trace),
            "acquisition-provenance.json": encode({"provenance_kind": "synthetic_fixture",
                                                    "diagnostic_fixture": True,
                                                    "reviewed_context_sha256": context["reviewed_context_sha256"]}),
            "capture/evidence.jsonl": rows(events),
            "capture/native/frames.jsonl": rows(frames),
            "capture/recorder_info.txt": "Create 7: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n",
        }
        files["capture/manifest.json"] = encode({"status": "draft", "acquisition": "original_live_run",
                                                  "case_id": entry["case_id"], "frames": n,
                                                  "extraction_confirmed": True,
                                                  "complete_driving_lanes": False,
                                                  "sources": {"road.xodr": sha_bytes(source["road.xodr"]),
                                                              "trace.jsonl": sha_bytes(files["trace.jsonl"])}})
        acquisition = {}
        for name in ("median-context.json", "divider-geometry.json", "ego-body-history.jsonl",
                     "observed-vehicle-history.jsonl",
                     "controller-history.jsonl", "video_frames.jsonl", "trace.jsonl",
                     "road.xodr", "reviewed-median-context.json", "authority-review-source.json"):
            acquisition[name] = {"kind": "diagnostic_fixture", "sha256": sha_bytes(files.get(name, source.get(name, "")))}
        files["acquisition.json"] = encode(acquisition)
        spec = {"files": files, "graphs": graph_specs, "videos": [
            {"path": camera["name"] + ".mkv", "frames": n, "width": camera["width"],
             "height": camera["height"], "fps": 20, "color": "black"}
            for camera in json.loads(source["config.json"])["cameras"]]}
        diagnostic = folder / "diagnostic.json"
        diagnostic.write_text(json.dumps(spec, separators=(",", ":"), ensure_ascii=False) + "\n")
        note = folder / "diagnostic-source-note.json"
        note.write_text(encode({"case_id": entry["case_id"], "scope": "synthetic diagnostic fixture; no physical or legal acceptance"}))
        recipe = {"format": "worker-fixture-recipe", "sources": [
            {"path": "diagnostic-source-note.json", "source": str(note.relative_to(REPO)), "sha256": sha(note)}],
            "generator": {"source": str(diagnostic.relative_to(REPO)), "sha256": sha(diagnostic)}}
        recipe_path = folder / "fixture-recipe.json"
        recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
        print(suffix, "source-bound diagnostic recipe")
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
