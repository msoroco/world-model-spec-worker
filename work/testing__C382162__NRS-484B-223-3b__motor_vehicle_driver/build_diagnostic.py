"""Nine-frame textual software diagnostics for each exact center-lane case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
KINDS = ("short_travel", "boundary_travel", "long_travel", "onto_highway_contrast")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def site(kind, road_hash):
    mode = "onto_highway" if kind == "onto_highway_contrast" else "from_highway"
    return {"public_highway_confirmed": True, "highway_road_id": "H",
            "driver_id": "fixture-driver", "ego_id": "fixture-driver",
            "ego_blueprint_id": "vehicle.fixture",
            "native_map_source": {"path": "native/map.json"},
            "highway_review_source": {"path": "native/review.json"},
            "lanes": [
                {"id": "C", "road_id": "H", "center_turn_lane": True,
                 "exclusive_turn_use": True,
                 "permitted_turn_directions": ["negative", "positive"],
                 "native_identity": {"road_id": 1, "lane_id": 0},
                 "centreline_xy_m": [[0, 0], [70, 0]],
                 "polygon_xy_m": [[0, -2], [70, -2], [70, 2], [0, 2]]},
                {"id": "E", "road_id": "H", "highway_through": True,
                 "native_identity": {"road_id": 1, "lane_id": 1},
                 "centreline_xy_m": [[0, 4], [40, 4]]},
                {"id": "W", "road_id": "H", "highway_through": True,
                 "native_identity": {"road_id": 1, "lane_id": -1},
                 "centreline_xy_m": [[40, -4], [0, -4]]}],
            "junction": {"id": "fixture-junction",
                         "kind": "street_intersection"},
            "route": {"center_lane_id": "C", "relationship": mode,
                      "approach_road_id": "S" if mode == "onto_highway" else "H",
                      "departure_road_id": "H" if mode == "onto_highway" else "S",
                      "side_lane_id": "S", "waypoints_xy_m": [[-20, 0], [0, 0], [20, 0]]},
            "road_aliases": {"1": "H", "2": "S"},
            "diagnostic_only": True, "road_sha256": road_hash}


def build():
    scaffold = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    scaffold["files"]["fixture-provenance.json"] = json.dumps({
        "scope": "CPU textual center-lane software compatibility only; no physical or legal evidence",
        "diagnostic_fixture": True}) + "\n"
    scaffold_path = HERE / "diagnostic-scaffold.json"
    scaffold_path.write_text(json.dumps(scaffold, sort_keys=True, separators=(",", ":")) + "\n")
    road = scaffold["files"]["road.xodr"]
    road_hash = hashlib.sha256(road.encode()).hexdigest()
    trace = [json.loads(line) for line in scaffold["files"]["trace.jsonl"].splitlines()]
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.removeprefix(AID + "__")
        if kind not in KINDS:
            raise ValueError("unknown exact center-lane diagnostic case")
        folder = HERE / "cases" / kind
        source_dir = folder / "diagnostic-sources"
        packet = site(kind, road_hash)
        map_record = {"opendrive_sha256": road_hash, "diagnostic_only": True}
        review = {"public_highway_confirmed": True,
                  "single_bidirectional_turn_only_center_lane": True,
                  "highway_road_id": "H",
                  "center_lane_polygon_xy_m": packet["lanes"][0]["polygon_xy_m"],
                  "diagnostic_only": True}
        values = {"native/map.json": map_record, "native/review.json": review}
        recipe_sources = []
        for name, value in values.items():
            path = source_dir / name
            write(path, value)
            key = "native_map_source" if name.endswith("map.json") else "highway_review_source"
            packet[key]["sha256"] = sha(path)
            recipe_sources.append({"path": name, "source": str(path.relative_to(REPO)),
                                   "sha256": sha(path)})
        history, frame_map = [], []
        target_feet = {"short_travel": 190, "boundary_travel": 200,
                       "long_travel": 210, "onto_highway_contrast": 210}[kind]
        target_m = target_feet / 3.280839895013123
        for index, row in enumerate(trace):
            onto = kind == "onto_highway_contrast"
            road_id = "S" if (onto and index == 0) or (not onto and index == 8) else "H"
            lane_id = "C" if 1 <= index <= 7 else "S" if road_id == "S" else "E"
            maneuver = "left_turn" if (onto and index == 1) or (not onto and index == 8) else "travel"
            x = -3 if index == 0 else 80 if index == 8 else .1 + (index - 1) * target_m / 6
            vertices = [[x + dx, dy, z] for z in (0, 1) for dx, dy in
                        ((-.2, -.2), (.2, -.2), (.2, .2), (-.2, .2))]
            original = {"original_frame": row["frame"], "time_s": row["time_s"],
                            "road_id": road_id, "lane_id": lane_id,
                            "maneuver": maneuver, "driver_id": "fixture-driver",
                            "source_ref": "native/diagnostic-route", "actor_id": 1,
                            "body_vertices_m": vertices,
                            "vehicle_blueprint": "vehicle.fixture",
                            "x": x, "y": 0.0,
                            "z": row["position"]["z"], "heading_x": 1.0,
                            "heading_y": 0.0, "speed_mps": row["speed_mps"]}
            original["source_sha256"] = hashlib.sha256(json.dumps(
                original, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            original["x_m"] = x
            original["y_m"] = 0.0
            history.append(original)
            camera_sources = {}
            for view in VIEWS:
                name = f"native/camera/{view}/{row['frame']:06d}.txt"
                path = source_dir / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"Synthetic diagnostic camera source {view} frame {row['frame']}\n")
                camera_sources[view] = {"path": name, "sha256": sha(path)}
                recipe_sources.append({"path": name, "source": str(path.relative_to(REPO)),
                                       "sha256": sha(path)})
            frame_map.append({"original_frame": row["frame"], "time_s": row["time_s"],
                              "camera_sources": camera_sources})
        refs = {}
        for key, name, value in (("site", "native/site.json", packet),
                                 ("history", "native/history.json", history),
                                 ("frame_map", "native/frame-map.json", frame_map)):
            path = source_dir / name
            write(path, value)
            refs[key] = {"path": name, "sha256": sha(path)}
            recipe_sources.append({"path": name, "source": str(path.relative_to(REPO)),
                                   "sha256": sha(path)})
        inventory = {"case_id": case_id, "source_kind": "original_native", "frame_count": 9,
                     "camera_views": list(VIEWS), "sources": refs,
                     "physical_acceptance_claimed": False}
        path = source_dir / "native/inventory.json"
        write(path, inventory)
        recipe_sources.append({"path": "native/inventory.json",
                               "source": str(path.relative_to(REPO)), "sha256": sha(path)})
        recipe_path = folder / "fixture-recipe.json"
        write(recipe_path, {"format": "worker-fixture-recipe",
                            "generator": {"source": str(scaffold_path.relative_to(REPO)),
                                          "sha256": sha(scaffold_path)},
                            "sources": recipe_sources})
        requirements = []
        keys = ("lane_design", "original_center_lane_distance",
                "left_turn_highway_relationship")
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if case_id in disposition["case_ids"]:
                requirements.append({"disposition_index": index,
                    "requirement": disposition["requirement"], "source": disposition["source"],
                    "output_key": keys[index], "method": "measure",
                    "value_type": "object", "kind": "measured",
                    "inputs": ["native/site.json",
                               "native/history.json", "native/frame-map.json", "road.xodr"]})
        contract = folder / "measurement-contract.json"
        write(contract, {"format": "worker-measurement-contract", "case_id": case_id,
                         "requirements": requirements,
                         "negative": {"remove": ["native/history.json"],
                                      "error_contains": "Missing required source: native/history.json"}})
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
        entry["measurement_contract"] = str(contract.relative_to(HERE))
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print(build())
