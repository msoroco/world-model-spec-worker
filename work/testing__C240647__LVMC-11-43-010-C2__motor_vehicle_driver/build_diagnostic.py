"""Build source-shaped nine-frame CPU fixtures for exact U-turn cases."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
KINDS = ("left_lane_u_turn", "outer_lane_u_turn")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _map():
    def lane(lane_id, radius):
        return {"lane_id": lane_id, "sample0": {"x": 0, "y": -radius},
                "sample1": {"x": 1, "y": -radius}, "route": [
                    {"x": -radius-2, "y": -radius, "section": "entry", "lane_id": lane_id},
                    {"x": 0, "y": -radius, "section": "ring", "lane_id": lane_id},
                    {"x": radius*.7071, "y": -radius*.7071, "section": "ring", "lane_id": lane_id},
                    {"x": radius, "y": 0, "section": "ring", "lane_id": lane_id},
                    {"x": radius*.7071, "y": radius*.7071, "section": "ring", "lane_id": lane_id},
                    {"x": 0, "y": radius, "section": "ring", "lane_id": lane_id},
                    {"x": -radius-2, "y": radius, "section": "exit", "lane_id": lane_id}]}
    return {"source_kind": "native_map_readback", "layout": "multilane_roundabout",
            "jurisdiction": "Las Vegas, Nevada", "map_id": "synthetic-fixture-map",
            "map_sha256": "a" * 64, "center": {"x": 0, "y": 0},
            "entry": {"prior": {"x": -8, "y": -3}, "junction": {"x": -4, "y": -3}},
            "exit": {"junction": {"x": -4, "y": 3}, "after": {"x": -8, "y": 3}},
            "lanes": {"left": lane("lane-inner", 2), "outer": lane("lane-outer", 4)}}


def build():
    scaffold = HERE / "diagnostic-scaffold.json"
    scaffold.write_bytes((REPO / "runtime/fixtures/example.json").read_bytes())
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        kind = case.removeprefix(AID + "__")
        if kind not in KINDS:
            raise ValueError("unknown exact U-turn fixture case")
        folder = HERE / "cases" / kind
        sources = folder / "diagnostic-sources"
        map_packet = _map()
        lane_id = "lane-inner" if kind == "left_lane_u_turn" else "lane-outer"
        frames = []
        for i in range(9):
            section = "entry" if i < 2 else "ring" if i < 7 else "exit"
            frames.append({"frame": i, "time_s": round(i*.05, 4), "section": section,
                           "lane_id": lane_id, "actor_id": "17", "heading_x": -1,
                           "heading_y": 0})
        history = {"source_kind": "sealed_native_original_history", "case_id": case,
                   "map_id": map_packet["map_id"], "map_sha256": map_packet["map_sha256"],
                   "actor_role": "motor_vehicle_driver", "actor_id": "17",
                   "intended_departure": "opposite_direction",
                   "vehicle_blueprint": "vehicle.fixture", "entry_id": "south-entry",
                   "exit_id": "north-exit", "controller_sha256": "b" * 64,
                   "weather_sha256": "c" * 64, "camera_plan_sha256": "d" * 64,
                   "frames": frames}
        recipe_sources = []
        refs = {}
        for name, packet in (("map", map_packet), ("history", history)):
            path = sources / (name + ".json")
            write(path, packet)
            refs[name] = {"path": path.name, "sha256": sha(path)}
            recipe_sources.append({"path": path.name,
                                   "source": str(path.relative_to(REPO)), "sha256": sha(path)})
        inventory = {"case_id": case, "source_kind": "original_native",
                     "frame_count": 9, "camera_views": list(VIEWS), "sources": refs}
        inventory_path = sources / "inventory.json"
        write(inventory_path, inventory)
        recipe_sources.append({"path": "inventory.json",
                               "source": str(inventory_path.relative_to(REPO)),
                               "sha256": sha(inventory_path)})
        recipe = {"format": "worker-fixture-recipe",
                  "generator": {"source": str(scaffold.relative_to(REPO)), "sha256": sha(scaffold)},
                  "sources": recipe_sources}
        recipe_path = folder / "fixture-recipe.json"
        write(recipe_path, recipe)
        requirements = []
        for index, key, method in ((0, "opposite_departure", "measure_opposite_departure"),
                                   (1, "lane_use", "measure_lane_use")):
            disposition = plan["requirement_dispositions"][index]
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "output_key": key, "method": method,
                                 "value_type": "object", "kind": "measured",
                                 "inputs": ["map.json", "history.json"]})
        contract = {"format": "worker-measurement-contract", "case_id": case,
                    "requirements": requirements,
                    "negative": {"remove": ["history.json"],
                                 "error_contains": "Missing required source: history.json"}}
        contract_path = folder / "measurement-contract.json"
        write(contract_path, contract)
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
        entry["measurement_contract"] = str(contract_path.relative_to(HERE))
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print(build())
