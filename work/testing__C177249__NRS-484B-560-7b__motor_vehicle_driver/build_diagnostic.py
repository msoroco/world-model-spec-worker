"""Build nine-frame instruction-shaped CPU fixtures, never original evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import railway_7b as law

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def site(name):
    authority, instruction, response = law.CASES[name]
    case = {"name": name, "authority": authority, "instruction": instruction,
            "response": response}
    return {"source_kind": "diagnostic_fixture_railway_7b_site",
            "law_id": law.LAW, "cell_id": law.CELL, "actor": law.ACTOR,
            "layout": "paved_road", "maneuver": "cross_railway", "control": "traffic_control_device",
            "_packet_sha256": "d" * 64,
            "map_sha256": "a" * 64,
            "native_readback": {key: "b" * 64 for key in
                ("rail_geometry_sha256", "road_geometry_sha256", "device_placement_sha256")},
            "crossing": {"grade_crossing": True,
                         **{key: "diagnostic:" + key for key in
                            ("rail_geometry_ref", "road_geometry_ref", "approach_lane_ref",
                             "crossing_entry_ref", "crossing_exit_ref")}},
            "vehicle": {"driver_role": law.ACTOR, "blueprint_id": "vehicle.carla.car",
                        "blueprint_source_ref": "diagnostic:blueprint",
                        "driver_identity_ref": "diagnostic:driver"},
            "device": {key: "diagnostic:" + key for key in
                       ("actor_or_map_id", "device_type", "placement_ref",
                        "erection_authority_ref", "traffic_purpose_ref",
                        "governed_movement_ref", "instruction_source_ref")},
            "officer": {"identity_ref": "diagnostic:officer",
                        "position_ref": "diagnostic:position",
                        "direction_channel_ref": "diagnostic:gesture"},
            "case": case}


def build():
    scaffold = HERE / "diagnostic-scaffold.json"
    scaffold.write_bytes((REPO / "runtime/fixtures/example.json").read_bytes())
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        name = case_id.removeprefix(AID + "__")
        if name not in law.CASES:
            raise ValueError("unknown railway fixture case")
        folder = HERE / "cases" / name
        sources = folder / "diagnostic-sources"
        sources.mkdir(parents=True, exist_ok=True)
        packet = site(name)
        law.validate_site(packet, name)
        frames, frame_map = [], []
        authority, instruction, response = law.CASES[name]
        for index in range(9):
            frame = 101 + index
            crossing = response == "cross"
            position_x = -8. + index * 1.5 if crossing else -8.
            body = [[position_x + dx, y, z] for dx in (-2., 2.)
                    for y in (-1., 1.) for z in (0., 1.5)]
            row = {"source_frame": frame, "source_frame_id": frame,
                   "time_s": round(index * .05, 5), "source_site_sha256": packet["_packet_sha256"],
                   "device_indication": instruction if authority == "device" else "clear",
                   "officer_direction": instruction if authority == "officer" else None,
                   "front_body_gap_to_entry_m": 6. - index * 1.5 if crossing else 6.,
                   "rear_body_gap_to_exit_m": -12. + index * 1.5 if crossing else -12.,
                   "speed_mps": 1.5 if crossing else 0.,
                   "velocity_mps": [1.5 if crossing else 0., 0., 0.],
                   "brake_applied": not crossing,
                   "vehicle_actor_id": 501, "vehicle_blueprint_id": "vehicle.carla.car",
                   "vehicle_position_m": [position_x, 0., .75],
                   "heading_xy": [1., 0.], "body_vertices_m": body,
                   **{key: "diagnostic:" + key for key in
                      ("device_indication_source_ref", "device_instruction_source_ref",
                       "governed_movement_source_ref", "body_source_ref", "control_source_ref",
                       "crossing_geometry_source_ref", "officer_direction_source_ref")}}
            frames.append(row)
            frame_map.append({"frame_index": index, "native_frame": frame,
                              "time_s": row["time_s"]})
        refs, recipe_sources = {}, []
        for key, filename, value in (("site", "site.json", packet),
                                     ("history", "history.json", frames),
                                     ("frame_map", "frame-map.json", frame_map)):
            path = sources / filename
            write(path, value)
            refs[key] = {"path": filename, "sha256": sha(path)}
            recipe_sources.append({"path": filename,
                                   "source": str(path.relative_to(REPO)), "sha256": sha(path)})
        inventory = {"case_id": case_id, "source_kind": "original_native",
                     "frame_count": 9, "camera_views": list(VIEWS),
                     "reviewed_site_sha256": packet["_packet_sha256"], "sources": refs}
        inventory_path = sources / "inventory.json"
        write(inventory_path, inventory)
        recipe_sources.append({"path": "inventory.json",
                               "source": str(inventory_path.relative_to(REPO)),
                               "sha256": sha(inventory_path)})
        recipe_path = folder / "fixture-recipe.json"
        write(recipe_path, {"format": "worker-fixture-recipe",
            "generator": {"source": str(scaffold.relative_to(REPO)), "sha256": sha(scaffold)},
            "sources": recipe_sources})
        requirements = []
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if case_id in disposition["case_ids"]:
                requirements.append({"disposition_index": index,
                    "requirement": disposition["requirement"], "source": disposition["source"],
                    "output_key": "railway_7b_requirement_" + str(index),
                    "method": "measure", "value_type": "object", "kind": "measured",
                    "inputs": ["site.json", "history.json", "frame-map.json"]})
        contract_path = folder / "measurement-contract.json"
        write(contract_path, {"format": "worker-measurement-contract",
            "case_id": case_id, "requirements": requirements,
            "negative": {"remove": ["history.json"],
                         "error_contains": "Missing required source: history.json"}})
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
        entry["measurement_contract"] = str(contract_path.relative_to(HERE))
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print(build())
