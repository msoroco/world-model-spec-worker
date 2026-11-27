"""Build nine-frame source-shaped railway CPU fixtures, never original evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import railway_7a as law

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
    axis, mode = law.CASE_AXES[name]
    case = {"name": name, "axis": axis, "mode": mode}
    if axis == "opposite_space":
        case.update(downstream_occupancy_source_ref="diagnostic:obstruction",
                    available_space_m=5. if mode == "halt" else 35.,
                    opposite_side_boundary_ref="diagnostic:edge")
    elif axis == "undercarriage":
        case.update(road_profile_source_ref="diagnostic:grade",
                    undercarriage_source_ref="diagnostic:bottom",
                    minimum_clearance_m=-.02 if mode == "halt" else .25)
    else:
        case["target_trailing_end_ft"] = {"below": 14.9, "at": 15., "above": 15.1}[mode]
    return {"source_kind": "diagnostic_fixture_railway_7a_site",
            "law_id": law.LAW, "cell_id": law.CELL, "actor": law.ACTOR,
            "layout": "paved_road", "maneuver": "cross_railway", "control": "rail_track",
            "source_sha256": "diagnostic-site-not-original",
            "_packet_sha256": "d" * 64,
            "crossing_axis_unit": [1., 0., 0.], "map_sha256": "a" * 64,
            "native_readback": {key: "b" * 64 for key in
                ("rail_geometry_source_sha256", "crossing_profile_source_sha256",
                 "downstream_space_source_sha256", "undercarriage_source_sha256")},
            "track": {"grade_crossing": True, "crossing_profile_ref": "diagnostic:profile",
                      "source_sha256": "c" * 64,
                      "rails": [{"rail_id": "near", "point_m": [0., 0., 0.],
                                 "tangent_unit": [0., 1., 0.],
                                 "original_geometry_ref": "diagnostic:rail-near"},
                                {"rail_id": "far", "point_m": [3., 0., 0.],
                                 "tangent_unit": [0., 1., 0.],
                                 "original_geometry_ref": "diagnostic:rail-far"}]},
            "vehicle": {"driver_role": law.ACTOR, "blueprint_id": "vehicle.carla.truck",
                        "blueprint_source_ref": "diagnostic:blueprint",
                        "bounding_box_source_ref": "diagnostic:bbox",
                        "undercarriage_geometry_ref": "diagnostic:bottom",
                        "dimensions_m": [8., 2.5, 3.], "coupled_units": []},
            "route_clearance_source_ref": "diagnostic:route",
            "approach_visibility_source_ref": "diagnostic:view",
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
        if name not in law.CASE_AXES:
            raise ValueError("unknown railway fixture case")
        folder = HERE / "cases" / name
        sources = folder / "diagnostic-sources"
        sources.mkdir(parents=True, exist_ok=True)
        packet = site(name)
        law.validate_site(packet, name)
        frames, frame_map = [], []
        for index in range(9):
            frame = 101 + index
            target = 14.9 if name == "trailing_end_14_9ft" else 15.0 if name == "trailing_end_15_0ft" else 15.1
            trailing = (3. + target * law.FOOT_M) if index >= 4 else 2. + index * .25
            halt = name.endswith("before_15ft") and index >= 4
            if halt:
                trailing = 3. + 14.0 * law.FOOT_M
            body = [[trailing + dx, y, z] for dx in (0., 8.)
                    for y in (-1.25, 1.25) for z in (0., 3.)]
            row = {"source_frame": frame, "source_frame_id": frame,
                   "time_s": round(index * .05, 5), "source_site_sha256": packet["_packet_sha256"],
                   "vehicle_units": [{"actor_id": "501", "blueprint_id": "vehicle.carla.truck",
                                      "body_source_ref": "diagnostic:bbox", "body_vertices_m": body,
                                      "position_m": [trailing + 4., 0., 1.5],
                                      "heading_xy": [1., 0.], "velocity_mps": [0. if halt else 1., 0., 0.]}],
                   "speed_mps": 0. if halt else 1.,
                   "downstream_body_gap_m": 0. if name == "space_halt_before_15ft" else 10.,
                   "undercarriage_contact": name == "clearance_grounded_before_15ft" and index >= 4,
                   "contact_source_ref": "diagnostic:contact",
                   "control_source_ref": "diagnostic:control",
                   "traffic_conflict_source_ref": "diagnostic:conflict",
                   "traffic_conflict": False, "brake_applied": False,
                   "vehicle_position_m": [trailing + 4., 0., 1.5],
                   "heading_xy": [1., 0.]}
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
                    "output_key": "railway_7a_requirement_" + str(index),
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
