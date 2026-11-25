"""Author explicit synthetic CPU fixtures for all five flashing-arrow cases."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SUFFIXES = ("arrow_clear", "arrow_ped_crosswalk", "arrow_ped_intersection",
            "arrow_vehicle_intersection", "arrow_concurrent_movement")


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def body(x, y):
    return [[x + dx, y + dy, 0.5] for dx, dy in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5))]


def build(suffix):
    if suffix not in SUFFIXES:
        raise ValueError("unknown exact arrow diagnostic case")
    fixture = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    files = fixture["files"]
    base_mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
    base_trace = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
    base_evidence = [json.loads(line) for line in files["capture/evidence.jsonl"].splitlines()]
    for name in ("trace.jsonl", "video_frames.jsonl", "body_history.jsonl",
                 "fixture-provenance.json"):
        files.pop(name, None)
    case_id = ASSIGNMENT + "__" + suffix
    route = [[0,-8],[0,-6],[0,-4],[0,-2],[0,0],[-2,0],[-4,0],[-6,0],[-8,0]]
    alternate = [[0,-8],[0,-6],[0,-4],[0,-2],[0,0],[0,2],[0,4],[0,6],[0,8]]
    concurrent = suffix == "arrow_concurrent_movement"
    source_docs = {
        "map.json": {"diagnostic": True, "map_name": "TownFixture"},
        "signal.json": {"diagnostic": True, "head_id": "17", "arrow": "left"},
        "route.json": {"route_xy": route, "diagnostic": True},
        "crosswalk.json": {"polygon_xy": [[3,-3],[6,-3],[6,3],[3,3]], "diagnostic": True},
    }
    if concurrent:
        source_docs["concurrent_route.json"] = {"route_xy": alternate,
                                                  "diagnostic": True}
    refs = []
    for name, value in source_docs.items():
        files[name] = encoded(value)
        refs.append({"path": name, "sha256": sha(files[name])})
    site = {"source_kind": "synthetic_fixture", "cell_id": "C111610",
            "actor": "motor_vehicle_driver", "case_id": case_id,
            "original_sources": refs,
            "map_source_path": "map.json", "signal_source_path": "signal.json",
            "route_source_path": "route.json", "crosswalk_source_path": "crosswalk.json",
            "native_map_name": "TownFixture", "official_head_id": "17",
            "ego_approach_id": "north", "facing_relation": True,
            "arrow_movement": "left", "ego_route_xy": route,
            "intersection_polygon_xy": [[-3,-3],[3,-3],[3,3],[-3,3]],
            "adjacent_crosswalk_polygon_xy": [[3,-3],[6,-3],[6,3],[3,3]],
            "signal_source_mode": "native_head_plus_external_aspect_packet"}
    if concurrent:
        site["concurrent_route_source_path"] = "concurrent_route.json"
        site["concurrent_route_xy"] = alternate
    files["site.json"] = encoded(site)
    aspects, events, trace, mapping, bodies = [], [], [], [], []
    for index in range(9):
        frame, time_s = base_mapping[index]["carla_frame"], base_mapping[index]["time_s"]
        x, y = (alternate if concurrent else route)[index]
        lit = index % 2 == 0
        indications = ["straight_green"] if concurrent else []
        aspects.append({"frame": frame, "elapsed_seconds": index / 20,
                        "head_id": "17", "facing_approach_id": "north",
                        "arrow_color": "yellow", "arrow_direction": "left",
                        "arrow_lit": lit, "source_kind": "controller_readback",
                        "source_id": "diagnostic-controller-17",
                        "native_head_state": "diagnostic-yellow-phase",
                        "concurrent_indications": indications})
        users = []
        if 2 <= index <= 4 and suffix.startswith("arrow_ped_"):
            users = [{"id": "ped-1", "kind": "pedestrian",
                      "xy": [4,0] if suffix == "arrow_ped_crosswalk" else [0,0],
                      "lawful_presence_source": "diagnostic-walk-entry"}]
        elif 2 <= index <= 4 and suffix == "arrow_vehicle_intersection":
            users = [{"id": "car-2", "kind": "motor_vehicle", "xy": [0,0],
                      "lawful_presence_source": "diagnostic-green-entry"}]
        heading = 0 if concurrent else min(90, index * 15)
        events.append({"frame": frame, "official_head_id": "17",
                       "facing_approach_id": "north",
                       "lit_aspects": ["flashing_yellow_turn_arrow"] if lit else [],
                       "arrow_movement": "left",
                       "ego_movement": "straight" if concurrent else "left",
                       "concurrently_permitted_movement": "straight" if concurrent else None,
                       "concurrent_permission_source": "diagnostic-controller-17" if concurrent else None,
                       "concurrent_indications": indications,
                       "ego_xy": [x,y], "ego_z_m": 0.5,
                       "ego_speed_mps": 0.0 if users else 2.0,
                       "ego_brake": 1.0 if users else 0.0,
                       "ego_heading_deg": heading,
                       "ego_body_vertices_m": body(x,y), "other_users": users})
        speed = 0.0 if users else 2.0
        radians = math.radians(-heading)
        velocity = [speed * math.cos(radians), speed * math.sin(radians), 0.0]
        traced = dict(base_trace[index])
        traced.update(frame=frame, time_s=time_s,
                      position={"x": x, "y": y, "z": 0.5},
                      position_m=[x,y,0.5], heading_deg=heading,
                      speed_mps=speed, speed_mph=speed / .44704,
                      velocity_mps=velocity)
        traced["control"] = dict(traced["control"], brake=1.0 if users else 0.0)
        trace.append(traced)
        base_evidence[index]["ego"].update(position_m=[x,y,0.5],
                                           heading_deg=heading,
                                           speed_mps=speed,
                                           body_vertices_m=body(x,y))
        participants = [actor for actor in
                        base_evidence[index]["original_observations"]["participants"]
                        if actor["actor_id"] == base_evidence[index]["actor_id"]]
        if len(participants) != 1:
            raise ValueError("base diagnostic participant identity changed")
        participants[0].update(position_m=[x,y,0.5], heading_deg=heading,
                               speed_mps=speed, velocity_mps=velocity,
                               body_vertices_m=body(x,y))
        fixture["graphs"][index]["attributes"]["observed_evidence"] = (
            base_evidence[index]["original_observations"])
        ego_nodes = [node for node in fixture["graphs"][index]["nodes"]
                     if node["attributes"].get("sem_class") == "ego"]
        if len(ego_nodes) != 1:
            raise ValueError("base diagnostic graph lacks one ego actor")
        attrs = ego_nodes[0]["attributes"]
        attrs.update(vertex=[x,y,0.5], threedbbox=body(x,y),
                     carla_speed=speed, carla_brake=1.0 if users else 0.0)
        attrs["forward"] = [math.cos(radians), math.sin(radians), 0]
        attrs["right"] = [-math.sin(radians), math.cos(radians), 0]
        attrs["original_observation"].update(position_m=[x,y,0.5],
                                             heading_deg=heading,
                                             speed_mps=speed,
                                             velocity_mps=velocity,
                                             body_vertices_m=body(x,y))
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": time_s})
        bodies.append({"frame": frame, "time_s": time_s,
                       "body_vertices_m": body(x,y), "heading_deg": heading})
    files["arrow-aspect-original.json"] = encoded(aspects)
    files["arrow-events-original.json"] = encoded(events)
    files["trace.jsonl"] = "".join(encoded(row) for row in trace)
    files["video_frames.jsonl"] = "".join(encoded(row) for row in mapping)
    files["body_history.jsonl"] = "".join(encoded(row) for row in bodies)
    files["capture/evidence.jsonl"] = "".join(encoded(row) for row in base_evidence)
    capture_manifest = json.loads(files["capture/manifest.json"])
    capture_manifest["sources"]["trace.jsonl"] = sha(files["trace.jsonl"])
    files["capture/manifest.json"] = encoded(capture_manifest)
    aspect_sha = sha(files["arrow-aspect-original.json"])
    event_sha = sha(files["arrow-events-original.json"])
    files["arrow-aspect-receipt.json"] = encoded({
        "format": "worker-original-arrow-aspect-v1",
        "source_path": "arrow-aspect-original.json", "source_sha256": aspect_sha,
        "frame_count": 9, "frequency_hz": 20, "first_frame": 38033,
        "head_id": "17", "facing_approach_id": "north",
        "arrow_direction": "left", "observed_transitions": 8,
        "diagnostic": True, "physical_acceptance": False})
    files["arrow-event-receipt.json"] = encoded({
        "format": "worker-original-arrow-event-v1",
        "event_ref": {"path": "arrow-events-original.json", "sha256": event_sha},
        "aspect_sha256": aspect_sha, "frame_count": 9, "diagnostic": True})
    files["arrow-camera-receipt.json"] = encoded({
        "format": "c111610-diagnostic-arrow-cameras-v1",
        "event_sha256": event_sha, "aspect_sha256": aspect_sha,
        "frame_count": 9, "diagnostic": True,
        "camera_sources": {name: {"path": name + ".mkv",
                                   "source_kind": "generated_diagnostic"}
                           for name in CAMERAS}})
    files["fixture-provenance.json"] = encoded({
        "scope": "synthetic CPU software compatibility only",
        "diagnostic_fixture": True, "physical_acceptance_claimed": False})
    files["acquisition-provenance.json"] = encoded({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "physical_acceptance_claimed": False})
    path = ROOT / ("diagnostic-" + suffix + ".json")
    path.write_text(json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) + "\n")
    assignment = REPO / "inputs" / ASSIGNMENT / "assignment.json"
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json",
                           "source": str(assignment.relative_to(REPO)),
                           "sha256": hashlib.sha256(assignment.read_bytes()).hexdigest()}],
              "generator": {"source": str(path.relative_to(REPO)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
    (ROOT / ("diagnostic-" + suffix + "-recipe.json")).write_text(
        json.dumps(recipe, indent=2) + "\n")
    return path


if __name__ == "__main__":
    for suffix in SUFFIXES:
        print(build(suffix))
