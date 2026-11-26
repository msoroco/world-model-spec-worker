"""Create source-shaped CPU fixtures, never physical Native evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
KINDS = ("cargo_active", "cargo_inactive", "passenger_active",
         "passenger_inactive", "opposite_side_control")
SOURCES = ("frame_map", "door", "activity", "passing_vehicle", "geometry")


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            raise ValueError("unknown exact diagnostic case")
        folder = HERE / "cases" / kind
        sources = folder / "diagnostic-sources"
        frames = [{"frame": 100 + i, "time_s": i / 20} for i in range(60)]
        activity_kind = "passenger" if kind.startswith("passenger") else "cargo"
        inactive = kind.endswith("inactive")
        side = "right" if kind == "opposite_side_control" else "left"
        packets = {
            "frame_map": {"case_id": case, "source_kind": "original_native", "frames": frames},
            "door": {"case_id": case, "source_kind": "original_native", "vehicle_id": "selected-1",
                     "samples": [dict(row, open=10 <= i < 40, side=side,
                                      angle_deg=70 if 10 <= i < 40 else 0)
                                 for i, row in enumerate(frames)]},
            "activity": {"case_id": case, "source_kind": "original_native", "vehicle_id": "selected-1",
                         "samples": [dict(row, active=10 <= i < (25 if inactive else 40),
                                          kind=activity_kind, loading_actor_id="load-1",
                                          speed_mps=.2 if 10 <= i < (25 if inactive else 40) else 0)
                                     for i, row in enumerate(frames)]},
            "passing_vehicle": {"case_id": case, "source_kind": "original_native",
                                "samples": [dict(row, vehicle_id="passing-1", center_x_m=-8 + i * .3,
                                                 center_y_m=2.2, width_m=1.5, length_m=4.0)
                                            for i, row in enumerate(frames)]},
            "geometry": {"source_kind": "original_native_geometry", "road_width_m": 6.0,
                         "selected_vehicle_center_x_m": 0.0, "selected_vehicle_center_y_m": 0.0,
                         "selected_vehicle_width_m": 2.0, "selected_vehicle_length_m": 4.0,
                         "selected_vehicle_id": "selected-1", "passing_vehicle_id": "passing-1",
                         "loading_position_supported": True}}
        inventory = {"case_id": case, "source_kind": "original_native", "sources": {}}
        recipe_sources = []
        for name in SOURCES:
            path = sources / (name + ".json")
            write(path, packets[name])
            inventory["sources"][name] = {"path": path.name, "sha256": sha(path)}
            recipe_sources.append({"path": path.name, "source": str(path.relative_to(REPO)),
                                   "sha256": sha(path)})
        inv_path = sources / "inventory.json"
        write(inv_path, inventory)
        recipe_sources.append({"path": "inventory.json", "source": str(inv_path.relative_to(REPO)),
                               "sha256": sha(inv_path)})
        recipe = {"format": "worker-fixture-recipe", "generator": {
                    "source": str(scaffold.relative_to(REPO)), "sha256": sha(scaffold)},
                  "sources": recipe_sources}
        recipe_path = folder / "fixture-recipe.json"
        write(recipe_path, recipe)
        requirements = []
        for index, output_key, method in ((0, "traffic_side", "measure_traffic_side"),
                                          (1, "loading_interval", "measure_loading_interval")):
            disposition = plan["requirement_dispositions"][index]
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "output_key": output_key, "method": method,
                                 "value_type": "object", "kind": "measured",
                                 "inputs": [name + ".json" for name in SOURCES]})
        contract = {"format": "worker-measurement-contract", "case_id": case,
                    "requirements": requirements,
                    "negative": {"remove": ["door.json"],
                                 "error_contains": "Missing required source: door.json"}}
        contract_path = folder / "measurement-contract.json"
        write(contract_path, contract)
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
        entry["measurement_contract"] = str(contract_path.relative_to(HERE))
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print(build())
