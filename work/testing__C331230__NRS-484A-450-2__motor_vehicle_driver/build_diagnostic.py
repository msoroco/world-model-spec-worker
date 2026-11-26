"""Build source-shaped nine-frame crosswalk CPU diagnostics for exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
KINDS = ("marked_crosswalk_halt", "marked_crosswalk_rolling",
         "unmarked_crosswalk_halt", "unmarked_crosswalk_rolling")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
FRONTS = (1., 3., 6., 9., 9.3, 10.1, 15., 15., 15.)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def site(kind):
    marked = kind.startswith("marked_")
    halt = kind.endswith("_halt")
    payload = {"source_kind": "diagnostic_fixture_crosswalk_site",
        "assignment_id": AID, "cell_id": "C331230", "actor": "motor_vehicle_driver",
        "qualifying_vehicle": True, "driver_control": True,
        "driver_id": "diagnostic-driver", "vehicle_id": "diagnostic-vehicle",
        "marked": marked, "halt": halt, "stop_sign_governs": True,
        "stop_sign_id": "S1", "stop_sign_orientation_xy": [-1., 0.],
        "map_sha256": "a" * 64, "road_id": 4, "lane_id": 1,
        "intersection_rect_m": [10., 0., 30., 20.],
        "near_crosswalk_rect_m": [8., 0., 10., 20.],
        "opposing_sidewalk_left_xy": [8., 0.],
        "opposing_sidewalk_right_xy": [8., 20.],
        "vehicle_route_xy": [[0., 10.], [20., 10.]],
        "crosswalk_entry_frame": 3}
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("near_crosswalk", HERE / "near_crosswalk.py")
    near = module_from_spec(spec)
    import sys
    sys.modules[spec.name] = near
    spec.loader.exec_module(near)
    for name in near.SOURCES:
        payload[name + "_source_sha256"] = hashlib.sha256(("diagnostic:" + name).encode()).hexdigest()
    return payload


def build():
    scaffold = HERE / "diagnostic-scaffold.json"
    scaffold.write_bytes((REPO / "runtime/fixtures/example.json").read_bytes())
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.removeprefix(AID + "__")
        if kind not in KINDS:
            raise ValueError("unknown exact crosswalk fixture case")
        folder = HERE / "cases" / kind
        sources = folder / "diagnostic-sources"
        packet = site(kind)
        frames, frame_map = [], []
        for index, front in enumerate(FRONTS):
            row = {"original_frame": 101 + index, "source_frame_id": 101 + index,
                   "time_s": round(index * .05, 5),
                   "driver_id": packet["driver_id"], "vehicle_id": packet["vehicle_id"],
                   "marked": packet["marked"], "stop_sign_governs": True,
                   "vehicle_front_xy": [front, 10.],
                   "speed_mps": 0. if packet["halt"] and index == 2 else 1.}
            row.update({name: value for name, value in packet.items()
                        if name.endswith("_source_sha256")})
            frames.append(row)
            frame_map.append({"frame_index": index,
                              "native_frame": 101 + index, "time_s": row["time_s"]})
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
                    "output_key": "near_crosswalk_approach", "method": "measure",
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
