"""Build nine-frame source-shaped CPU fixtures for exact speed/posting cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
KINDS = ("same25_below", "same25_at", "same25_above", "different35")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
STATIONS = (0, 20, 40, 50, 60, 70, 80, 90, 100)
TARGETS = {"same25_below": 20.0, "same25_at": 25.0,
           "same25_above": 30.0, "different35": 30.0}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def site(kind):
    value = 35 if kind == "different35" else 25
    sign = {"sign_id": "S1", "value_mph": value,
            "source": "diagnostic-fixture/sign", "direction": "route",
            "governed_start_station_m": 40.0, "governed_end_station_m": 120.0,
            "time_conditions_source": "diagnostic-fixture/daytime"}
    return {"source_kind": "diagnostic_fixture_speed_site", "law_id": "LVMC-11-16-060",
            "cell_id": "C150979", "map_sha256": "a"*64, "map_name": "FixtureTown",
            "municipal_jurisdiction_source": "diagnostic-fixture/jurisdiction",
            "covered_street_source": "diagnostic-fixture/street", "road_kind": "street",
            "route": {"road_id": 3, "lane_id": 1, "one_way_source": "diagnostic-fixture/map",
                      "spawn_station_m": 0.0, "end_station_m": 120.0},
            "start_xyz": [0.0, 0.0, 0.0],
            "sign_inventory_complete_source": "diagnostic-fixture/complete",
            "sign_inventory_extent_m": [0.0, 120.0],
            "title_posting_review_source": "diagnostic-fixture/not-legal-authority",
            "signs": [sign]}


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
            raise ValueError("unknown exact speed fixture case")
        folder = HERE / "cases" / kind
        sources = folder / "diagnostic-sources"
        packet = site(kind)
        frames = []
        frame_map = []
        for i, station in enumerate(STATIONS):
            row = {"frame_index": i, "source_frame_id": 101+i,
                   "time_s": round(i*.05, 4), "ego_alive": True,
                   "driver_role": "motor_vehicle_driver", "map_sha256": packet["map_sha256"],
                   "route_station_m": station, "speed_mps": TARGETS[kind]*.44704}
            if station >= 40:
                row.update(sign_id="S1", sign_value_mph=packet["signs"][0]["value_mph"])
            frames.append(row)
            frame_map.append({"frame_index": i, "native_frame": 101+i,
                              "time_s": row["time_s"]})
        refs = {}
        recipe_sources = []
        for name, filename, value in (("site", "site.json", packet),
                                      ("history", "history.json", frames),
                                      ("frame_map", "frame-map.json", frame_map)):
            path = sources / filename
            write(path, value)
            refs[name] = {"path": filename, "sha256": sha(path)}
            recipe_sources.append({"path": filename, "source": str(path.relative_to(REPO)),
                                   "sha256": sha(path)})
        inventory = {"case_id": case, "source_kind": "original_native",
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
            if case not in disposition["case_ids"]:
                continue
            requirements.append({"disposition_index": index,
                "requirement": disposition["requirement"], "source": disposition["source"],
                "output_key": "observed_speed", "method": "measure",
                "value_type": "object", "kind": "measured", "inputs": ["site.json", "history.json", "frame-map.json"]})
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
