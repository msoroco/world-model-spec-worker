"""Build source-shaped synthetic compatibility recipes for exact freight cases."""
from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path

from freight_zone import CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
DONOR = ROOT / "work/testing__C135087__NRS-484B-517__motor_vehicle_driver/diagnostics"
SOURCE = DONOR / "loading_open_waiting"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
                               separators=(",", ":") if compact else None,
                               indent=None if compact else 2) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("returned freight diagnostic exceeds 2 MiB: " + str(path))


def synthetic_site(case, exact, source_sha):
    return {
        "case_id": exact, "source_kind": "synthetic_diagnostic_fixture",
        "accepted_original_source": False, "cell_id": "C386226", "layout": "one_way_road",
        "road": {"source_sha256": source_sha, "one_way_readback": True,
                 "approach_waypoints": [[0, 0], [1, 0]], "freight_entry_waypoint": [0, 1],
                 "freight_entry_source_sha256": source_sha},
        "zone": {"designation": "freight_curb_loading", "marking_source_sha256": source_sha,
                 "boundary_source_sha256": source_sha, "curb_adjacency_source_sha256": source_sha,
                 "parking_pose_source_sha256": source_sha,
                 "polygon_xy": [[2, -2], [6, -2], [6, 2], [2, 2]],
                 "parking_pose": [4, 0], "materials_anchor": [4, 1], "passenger_anchor": [4, -1]},
        "clock": {"source_sha256": source_sha,
                  "civil_time_iso": "2026-11-26T12:00:00-08:00" if case.hours == "effective" else "2026-11-26T03:00:00-08:00",
                  "timezone": "America/Los_Angeles"},
        "regulations": {"source_sha256": source_sha,
                        "effective_hours_source_sha256": source_sha,
                        "jurisdiction": "synthetic protocol only",
                        "effective_at_civil_time": case.hours == "effective"},
        "vehicle_blueprint": "synthetic_ego_car", "vehicle_blueprint_source_sha256": source_sha,
        "driver_responsibility_source_sha256": source_sha,
        "materials_inventory": ["synthetic_box"], "materials_inventory_source_sha256": source_sha,
        "freight_vehicle_blueprint": "synthetic_freight_car",
        "freight_vehicle_blueprint_source_sha256": source_sha,
        "passenger_blueprint": "synthetic_passenger", "passenger_blueprint_source_sha256": source_sha,
        "activity_controller_source_sha256": source_sha,
        "traffic_and_official_directions_source_sha256": source_sha,
    }


def synthetic_rows(case, exact, source_sha):
    rows = []
    start = 280 + round(case.activity_delay_s * 20)
    for frame in range(900):
        row = {"case_id": exact, "original_frame": frame, "elapsed_s": frame / 20,
               "ego_id": "ego", "driver_id": "driver", "materials_id": "materials",
               "passenger_id": "passenger", "freight_vehicle_id": "freight_vehicle",
               "map_sha256": source_sha, "zone_source_sha256": source_sha,
               "regulations_source_sha256": source_sha, "clock_source_sha256": source_sha,
               "traffic_and_official_directions_source_sha256": source_sha,
               "camera_plan_sha256": source_sha, "source_sha256": source_sha,
               "control_source_sha256": source_sha,
               "ego_center_xy": [4, 0] if 280 <= frame < 600 else [1, 0],
               "ego_speed_mps": 0 if 280 <= frame < 600 else 3,
               "freight_center_xy": [0, 1], "freight_entry_blocked": False,
               "material_event": None, "passenger_event": None, "freight_event": None}
        if case.material_action == "pickup_load":
            if frame == start:
                row.update(material_event="pickup_started", material_event_source_sha256=source_sha)
            if frame == start + 10:
                row.update(material_event="loading_started", material_event_source_sha256=source_sha)
            if frame == start + 60:
                row.update(material_event="loading_completed", material_event_source_sha256=source_sha)
        if case.material_action == "unload_deliver":
            if frame == start:
                row.update(material_event="unloading_started", material_event_source_sha256=source_sha)
            if frame == start + 60:
                row.update(material_event="delivery_completed", material_event_source_sha256=source_sha)
        if case.passenger_action == "board" and frame in (300, 340):
            row.update(passenger_event="boarding_started" if frame == 300 else "boarding_completed",
                       passenger_event_source_sha256=source_sha)
        if case.passenger_action == "alight" and frame in (300, 340):
            row.update(passenger_event="alighting_started" if frame == 300 else "alighting_completed",
                       passenger_event_source_sha256=source_sha)
        if case.freight_arrival != "none" and frame == 290:
            row.update(freight_event="waiting_to_enter" if case.freight_arrival == "waiting" else "about_to_enter",
                       freight_event_source_sha256=source_sha)
        if case.freight_arrival != "none" and 300 <= frame < 380:
            row.update(freight_entry_blocked=True,
                       freight_entry_blocked_source_sha256=source_sha)
        rows.append(row)
    return rows


def build():
    donor = json.loads((DONOR / "loading_open_waiting-generator.json").read_text())
    source_note = HERE / "diagnostic-source-note.json"
    dump(source_note, {"format": "c386226-freight-synthetic-source-v1",
                       "source_kind": "synthetic_diagnostic_fixture", "accepted_original_source": False,
                       "case_ids": [AID + "__" + c.name for c in CASES]})
    source_sha = sha(source_note)
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    diagnostic = []
    for case in CASES:
        exact = AID + "__" + case.name
        production = next(e for e in manifest["cases"] if e["case_id"] == exact)
        construction = json.loads((HERE / production["construction"]).read_text())
        files = {entry["path"]: entry["content"] for entry in construction["files"]}
        config = json.loads(files["config.json"])
        files["config.json"] = json.dumps(config, indent=2) + "\n"
        files["scene.json"] = json.dumps(synthetic_site(case, exact, source_sha), indent=2) + "\n"
        files["analysis.py"] = (HERE / "analysis.py").read_text()
        construction["files"] = [{"path": path, "content": content} for path, content in files.items()]
        construction["diagnostic_only"] = True
        construction_path = HERE / ("construction-compatibility-" + case.name + ".json")
        dump(construction_path, construction)
        folder = HERE / "diagnostics" / case.name
        folder.mkdir(parents=True, exist_ok=True)
        rows_path = folder / "freight-rows.json"
        dump(rows_path, synthetic_rows(case, exact, source_sha), compact=True)
        copied = []
        for relative in ("trace.jsonl", "video_frames.jsonl", "capture/native/frames.jsonl", "capture/evidence.jsonl"):
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SOURCE / relative).read_bytes())
            copied.append({"path": relative, "source": str(target.relative_to(ROOT)), "sha256": sha(target)})
        provenance = folder / "acquisition-provenance.json"
        dump(provenance, {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                          "scope": "freight source-shaped CPU software diagnostic only"})
        for target in (rows_path, source_note, provenance):
            copied.append({"path": target.name, "source": str(target.relative_to(ROOT)), "sha256": sha(target)})
        generator = copy.deepcopy(donor)
        generator["files"]["capture/manifest.json"] = json.dumps({
            "acquisition": "synthetic_fixture", "case_id": exact,
            "extraction_confirmed": True, "frames": 900,
            "observation_contract_version": 2, "required_observations": [],
            "complete_driving_lanes": True,
            "native_map_facts": {"path": "native_map_facts.json",
                                 "sha256": hashlib.sha256(generator["files"]["capture/native_map_facts.json"].encode()).hexdigest()},
            "sources": {"road.xodr": hashlib.sha256(generator["files"]["road.xodr"].encode()).hexdigest(),
                        "trace.jsonl": sha(folder / "trace.jsonl")}}, indent=2) + "\n"
        generator_path = HERE / "diagnostics" / (case.name + "-generator.json")
        dump(generator_path, generator, compact=True)
        recipe_path = HERE / "diagnostics" / (case.name + "-recipe.json")
        dump(recipe_path, {"format": "worker-fixture-recipe", "sources": copied,
                           "generator": {"source": str(generator_path.relative_to(ROOT)),
                                         "sha256": sha(generator_path)}})
        contract_path = HERE / "diagnostics" / (case.name + "-measurement-contract.json")
        dump(contract_path, {"format": "worker-measurement-contract", "case_id": exact,
                             "requirements": [{"disposition_index": 0,
                                               "requirement": "NRS-484B-507-1",
                                               "source": "inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json",
                                               "output_key": "freight_curb_zone", "method": "measure_freight_zone",
                                               "value_type": "object", "kind": "measured",
                                               "inputs": ["freight-rows.json", "diagnostic-source-note.json"]}],
                             "negative": {"remove": ["freight-rows.json"],
                                          "error_contains": "Missing required source: freight-rows.json"}})
        diagnostic.append({"case_id": exact, "kind": "capability_research",
                           "construction": construction_path.name,
                           "construction_sha256": sha(construction_path),
                           "fixture_recipe": str(recipe_path.relative_to(ROOT)),
                           "measurement_contract": str(contract_path.relative_to(HERE)),
                           "measurement_procedure": {"entrypoint": "analysis.py"}})
    dump(HERE / "execution-manifest.compatibility-diagnostic.json",
         {"format": "worker-execution-manifest", "assignment_id": AID,
          "status": "synthetic_compatibility_only",
          "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
          "cases": diagnostic})


if __name__ == "__main__":
    build()
