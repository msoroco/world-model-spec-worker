"""Build source-shaped Native bypass fixtures; these are synthetic diagnostics."""
import hashlib
import json
from pathlib import Path

from native_scene import CAMERAS, FRAMES, geometry, open_drive, request

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
BASE = ROOT / "work/training__C10316__NRS-484B-283-1d3__pedestrian/diagnostic30-controlled_1.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def lines(values):
    return "".join(json.dumps(value, separators=(",", ":"),
                              allow_nan=False) + "\n" for value in values)


def body(x, y):
    return [[round(x + dx, 6), round(y + dy, 6)]
            for dx, dy in ((-.16, -.16), (-.16, .16), (.16, -.16), (.16, .16))]


def body3(x, y):
    return [[round(x + dx, 6), round(y + dy, 6), z]
            for dx, dy in ((-.16, -.16), (-.16, .16), (.16, -.16), (.16, .16))
            for z in (0, 1.8)]


def build():
    original = json.loads(BASE.read_text())
    manifest = json.loads((HERE / "selected-draft-manifest.json").read_text())
    for item in manifest["cases"]:
        condition = item["case_id"].rsplit("__", 1)[-1]
        layout = geometry(condition)
        for candidate, shift in (("primary", 0.0), ("fallback1", .08)):
            spec = {"files": {key: value for key, value in original["files"].items()
                              if key not in ("no-countdown-context.json",
                                             "no-countdown-samples.jsonl")},
                    "graphs": original["graphs"], "videos": original["videos"]}
            trace = rows(spec["files"]["trace.jsonl"])
            evidence = rows(spec["files"]["capture/evidence.jsonl"])
            frames = rows(spec["files"]["capture/native/frames.jsonl"])
            mapping = rows(spec["files"]["video_frames.jsonl"])
            if not len(trace) == len(evidence) == len(frames) == len(mapping) == len(spec["graphs"]) == FRAMES:
                raise ValueError("base source-shaped fixture lacks complete frame coverage")
            people, camera_rows = [], []
            for index in range(FRAMES):
                row = request(condition, index, lateral_shift_m=shift)
                x, y = row["target_xy_m"]
                frame, time = index + 100, index / 20
                velocity = [row["walker_direction_xyz"][0] * row["walker_speed_mps"],
                            row["walker_direction_xyz"][1] * row["walker_speed_mps"], 0]
                heading = 180 if condition == "direction_west" else 0
                trace[index].update(frame=frame, time_s=time,
                                    position={"x": x, "y": y, "z": .5},
                                    position_m=[x, y, .5], heading_deg=heading,
                                    speed_mps=row["walker_speed_mps"],
                                    speed_mph=row["walker_speed_mps"] * 2.2369362921,
                                    velocity_mps=velocity)
                evidence[index].update(original_frame=frame, replay_frame=frame,
                    recording_time_s=time, replay_simulation_time_s=time)
                evidence[index]["ego"].update(position_m=[x, y, .5],
                    heading_deg=heading, speed_mps=row["walker_speed_mps"],
                    body_vertices_m=body3(x, y))
                graph = spec["graphs"][index]
                graph["attributes"].update(frame=frame, simulation_time_s=time,
                    source="C109128 synthetic blocked-sidewalk diagnostic source shape")
                graph["nodes"][0]["attributes"].update(vertex=[x, y, .5],
                    forward=row["walker_direction_xyz"], threedbbox=body3(x, y))
                frames[index].update(frame=frame, time_s=time,
                    simulation_time=time,
                    adapter_graph=f"graphs/base/{frame:08d}.adapter.json")
                graph["path"] = f"capture/native/graphs/base/{frame:08d}.adapter.json"
                hashes = {name: "a" * 64 for name, *_ in CAMERAS}
                mapping[index].update(video_frame=index, native_frame=frame,
                                      carla_frame=frame, time_s=time,
                                      source_rgb_sha256=hashes)
                people.append({"video_frame": index, "native_frame": frame,
                    "time_s": time, "walker_id": 107,
                    "center_xy_m": [x, y], "footprint_xy_m": body(x, y),
                    "requested_target_xy_m": [x, y],
                    "requested_bypass_path": condition,
                    "original_native_observed": True,
                    "synthetic_diagnostic": True,
                    "physical_or_legal_verdict": None})
                for name, width, height, *_ in CAMERAS:
                    camera_rows.append({"camera": name, "video_frame": index,
                        "native_frame": frame, "time_s": time,
                        "width": width, "height": height,
                        "source_path": name + ".mkv",
                        "source_rgb_sha256": hashes[name]})
            for name, data in (("trace.jsonl", trace),
                               ("capture/evidence.jsonl", evidence),
                               ("capture/native/frames.jsonl", frames),
                               ("video_frames.jsonl", mapping),
                               ("pedestrian-original.jsonl", people),
                               ("camera-sources.jsonl", camera_rows)):
                spec["files"][name] = lines(data)
            scene = {"source_kind": "original_native_map_readback",
                     "synthetic_diagnostic": True,
                     "lanes": {name: [{"x_requested_m": 25,
                                       "native_xyz_m": [25, y, .4],
                                       "lane_type": name}]
                               for name, y in ([('roadway', -1.75),
                                                ('bicycle', -4.0),
                                                ('shoulder', -4.75),
                                                ('sidewalk', -6.0)] if layout["bicycle"] else
                                               [('roadway', -1.75),
                                                ('shoulder', -3.75),
                                                ('sidewalk', -5.0)])},
                     "sidewalk_y_m": list(layout["sidewalk"]),
                     "shoulder_y_m": list(layout["shoulder"]),
                     "roadway_y_m": [-3.5, 0],
                     "bike_lane_designation": "native_biking_lane" if layout["bicycle"] else "absent",
                     "bicycle_y_m": list(layout["bicycle"]) if layout["bicycle"] else None,
                     "road_direction": layout["road_direction"],
                     "walking_direction_requested": layout["walking_direction"],
                     "intervening_area_requested_impassable":
                         layout["intervening_area_requested_impassable"],
                     "legal_highway_status_review_pending": True,
                     "obstruction_actors": [{"native_actor_id": i,
                        "native_type_id": "synthetic.static.prop.streetbarrier",
                        "native_xyz_m": [21 + i // 2 * 2,
                                         (-6.4 if i % 2 == 0 else -5.8) if layout["bicycle"] else
                                         (-5.4 if i % 2 == 0 else -4.8), .1],
                        "extent_xyz_m": [1.1, .4, .6]} for i in range(10)]}
            if layout["intervening_area_requested_impassable"]:
                scene["obstruction_actors"].extend({
                    "native_actor_id": 10 + i,
                    "native_type_id": "synthetic.static.prop.streetbarrier",
                    "native_xyz_m": [21 + i * 2, -4.75, .1],
                    "extent_xyz_m": [1.1, .4, .6]} for i in range(5))
            scene["sidewalk_context"] = {
                "source_kind": "synthetic_diagnostic_map_readback",
                "roadway_lane_count": 1,
                "sidewalk_lane_count": 1,
                "obstruction_actor_count": len(scene["obstruction_actors"]),
                "legal_status_review_pending": True,
            }
            spec["files"]["sidewalk_context.json"] = json.dumps(scene,
                separators=(",", ":")) + "\n"
            road = open_drive(condition)
            spec["files"]["road.xodr"] = road
            spec["files"]["capture/manifest.json"] = json.dumps({
                "extraction_confirmed": True, "frames": FRAMES,
                "required_observations": [], "sources": {
                    "trace.jsonl": hashlib.sha256(spec["files"]["trace.jsonl"].encode()).hexdigest(),
                    "road.xodr": hashlib.sha256(road.encode()).hexdigest()},
                "synthetic_diagnostic": True}, separators=(",", ":")) + "\n"
            for video in spec["videos"]:
                video["frames"] = FRAMES
            destination = ASSIGNMENT / f"diagnostic-{condition}-{candidate}.json"
            destination.write_text(json.dumps(spec, separators=(",", ":"),
                                              allow_nan=False) + "\n")
            if destination.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("diagnostic fixture exceeds 2 MiB return limit")
            recipe = {"format": "worker-fixture-recipe", "sources": [{
                "path": "diagnostic-input.json",
                "source": str(destination.relative_to(ROOT)),
                "sha256": sha(destination)}],
                "generator": {"source": str(destination.relative_to(ROOT)),
                              "sha256": sha(destination)}}
            recipe_path = ASSIGNMENT / f"diagnostic-{condition}-{candidate}-recipe.json"
            recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
            print(json.dumps({"condition": condition, "candidate": candidate,
                              "spec_bytes": destination.stat().st_size,
                              "recipe_sha256": sha(recipe_path)}))


if __name__ == "__main__":
    build()
