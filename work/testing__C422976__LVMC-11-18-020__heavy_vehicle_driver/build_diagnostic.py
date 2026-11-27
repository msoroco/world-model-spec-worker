"""Build nine-frame source-shaped School-Xing CPU fixtures for exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import school_crossing as school


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def site(case, records):
    return {"source_kind": "diagnostic_fixture_school_crossing_site",
        "assignment_id": AID, "law_id": school.LAW, "cell_id": "C422976",
        "catalog_control": "school_crosswalk",
        "case_ids": [AID + "__" + c.name for c in school.CASES],
        "source_records": records, "jurisdiction": "Las Vegas municipal",
        "engineer_opinion_source": "municipal_authority.txt",
        "sign_necessity_source": "municipal_authority.txt",
        "operator_id": "diagnostic-driver", "vehicle_id": "501",
        "vehicle_class": "heavy_vehicle", "vehicle_blueprint": "vehicle.carla.truck",
        "vehicle_dimensions_m": {"length": 7.0, "width": 2.5, "height": 3.0},
        "route_clearance_reviewed": True,
        "intersection_status": "intersection", "school_vicinity_reviewed": True,
        "crossing_rect_m": [0., -3., 4., 3.],
        "roadway_rect_m": [-30., -4., 30., 4.],
        "crossing_width_ft": 12.0, "crossing_marking": case.crossing_marking,
        "sign": {"words": "School-Xing", "conspicuous_reviewed": True,
                 "placement": case.sign_placement,
                 "advance_distance_ft": case.sign_distance_ft,
                 "displayed": case.sign_displayed},
        "person": {"id": "601", "side_relative_to_approach": case.person_side,
                   "attempt_evidence_source": "pedestrian_source.txt",
                   "attempt_requested": case.person_attempt},
        "approach_direction_xy": [1., 0.], "opposing_direction_xy": [-1., 0.],
        "road_id": 1, "lane_id": -1, "map_sha256": "a" * 64,
        "crossing_id": "crossing-1", "sign_id": "school-sign-1"}


def build():
    scaffold = HERE / "diagnostic-scaffold.json"
    scaffold.write_bytes((REPO / "runtime/fixtures/example.json").read_bytes())
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        case = next((c for c in school.CASES if case_id == AID + "__" + c.name), None)
        if case is None:
            raise ValueError("unknown exact School-Xing diagnostic case")
        folder = HERE / "cases" / case.name
        sources = folder / "diagnostic-sources"
        sources.mkdir(parents=True, exist_ok=True)
        records = {}
        for name in school.SOURCES:
            path = sources / (name + ".txt")
            path.write_text("Diagnostic source placeholder for " + name + "; not original evidence.\n")
            records[name] = {"path": path.name, "sha256": sha(path)}
        packet = site(case, records)
        frames, frame_map = [], []
        for index in range(9):
            frame = 101 + index
            front = -1.0 if not case.entry_requested or index < 4 else .5 + .2 * (index - 4)
            row = {"original_frame": frame, "source_frame_id": frame,
                   "time_s": round(index * .05, 5), "native_source": False,
                   "actor_id": packet["vehicle_id"], "person_id": packet["person"]["id"],
                   "driver_id": packet["operator_id"],
                   "road_id": packet["road_id"], "lane_id": packet["lane_id"],
                   "vehicle_front_xy": [front, 0.],
                   "person_xy": [2., -2. if case.person_side == "approach_side" else 2.],
                   "sign_displayed": case.sign_displayed,
                   "person_attempt_source_sha256": records["pedestrian_source"]["sha256"],
                   "person_attempt_observed": case.person_attempt,
                   "person_side_relative_to_approach": case.person_side}
            frames.append(row)
            frame_map.append({"frame_index": index, "native_frame": frame,
                              "time_s": row["time_s"]})
        refs, recipe_sources = {}, []
        for name, filename, value in (("site", "site.json", packet),
                                      ("history", "history.json", frames),
                                      ("frame_map", "frame-map.json", frame_map)):
            path = sources / filename
            write(path, value)
            refs[name] = {"path": filename, "sha256": sha(path)}
            recipe_sources.append({"path": filename,
                                   "source": str(path.relative_to(REPO)), "sha256": sha(path)})
        inventory = {"case_id": case_id, "source_kind": "original_native",
                     "frame_count": 9, "camera_views": list(VIEWS), "sources": refs}
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
                    "output_key": "school_crossing_entry_" + str(index), "method": "measure",
                    "value_type": "object", "kind": "measured",
                    "inputs": ["site.json", "history.json", "frame-map.json"]})
        contract_path = folder / "measurement-contract.json"
        write(contract_path, {"format": "worker-measurement-contract", "case_id": case_id,
            "requirements": requirements,
            "negative": {"remove": ["history.json"],
                         "error_contains": "Missing required source: history.json"}})
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
        entry["measurement_contract"] = str(contract_path.relative_to(HERE))
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print(build())
