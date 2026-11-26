"""Bind case-specific synthetic source diagnostics to selected measurements."""

import hashlib
import json
from pathlib import Path

from package_spec import AID


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"
EXAMPLE = ROOT / "runtime" / "fixtures" / "example.json"
METHODS = ((0, "activation", "measure_activation"),
           (1, "due_care_sources", "measure_due_care_sources"),
           (2, "lane_topology", "measure_topology"),
           (3, "lane_movement", "measure_lane_movement"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, *, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"separators": (",", ":")} if compact else {"indent": 2}
    path.write_text(json.dumps(value, ensure_ascii=False, **kwargs) + "\n", encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic specification exceeds return file limit")


def body(x):
    return [[x + dx, dy, z] for z in (-.3, .3) for dy in (-.3, .3)
            for dx in (-.3, .3)]


def build():
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    base_frames = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines()]
    if len(base_frames) != 9:
        raise ValueError("pinned diagnostic example frame shape changed")
    dispositions = plan["requirement_dispositions"]
    for entry, case in zip(manifest["cases"], plan["cases"]):
        if entry["case_id"] != case["case_id"]:
            raise ValueError("selected exact case order changed")
        suffix = case["case_id"].removeprefix(AID + "__")
        spec = json.loads(json.dumps(base))
        two = case["same_direction_lane_count_requested"] == 2
        left = "left" if two else None
        occupied = case["left_lane_traffic_requested"] == "occupied"
        move = case["ego_maneuver_request"] == "move_left" and not occupied
        same_lanes = [{"lane_id": "right", "forward": [1, 0],
                       "source_ref": "synthetic-diagnostic-right-lane",
                       "immediate_left_lane_id": left}]
        if two:
            same_lanes.append({"lane_id": "left", "forward": [1, 0],
                               "source_ref": "synthetic-diagnostic-left-lane"})
        context = {"case_id": case["case_id"],
                   "map_sha256": sha(ROOT / "runtime" / "fixtures" / "example.json"),
                   "ego_kind": "motor_vehicle", "control_kind": case["control_kind"],
                   "ego_driver_source": "synthetic-diagnostic-driver",
                   "control_rider_source": "synthetic-diagnostic-rider",
                   "road_origin": [0, 0], "road_forward": [1, 0],
                   "lanes": same_lanes, "ego_initial_lane_id": "right",
                   "control_initial_lane_id": "right", "immediate_left_lane_id": left,
                   "lane_restrictions_source": "synthetic-diagnostic-lane-rules",
                   "left_lane_traffic_source": "synthetic-diagnostic-actor-inventory",
                   "left_lane_obstructions_source": "synthetic-diagnostic-obstruction-inventory",
                   "surrounding_trajectories_source": "synthetic-diagnostic-trajectory-inventory"}
        rows = []
        for i, mapping in enumerate(base_frames):
            frame, time_s = mapping["carla_frame"], mapping["time_s"]
            ego_x = 2.5 * i if case["ego_maneuver_request"] != "follow" and not occupied else .2 * i
            control_x = 8 + .2 * i
            rows.append({"frame": frame, "time_s": time_s,
                         "ego_vertices": body(ego_x), "control_vertices": body(control_x),
                         "ego_lane_id": "left" if move and i >= 3 else "right",
                         "control_lane_id": "right",
                         "left_lane_occupied_actor_ids": ["synthetic-other"] if occupied else [],
                         "ego_speed_mps": 5 if not occupied else .2,
                         "control_speed_mps": .2})
        context_text = json.dumps(context, sort_keys=True) + "\n"
        trace_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        receipt = {"assignment_id": AID, "case_id": case["case_id"],
                   "source_kind": "synthetic_diagnostic_fixture",
                   "diagnostic_fixture": True, "fps": 20, "frame_count": len(rows),
                   "context_sha256": hashlib.sha256(context_text.encode()).hexdigest(),
                   "trace_sha256": hashlib.sha256(trace_text.encode()).hexdigest(),
                   "physical_acceptance": False, "legal_verdict": None}
        spec["files"].update({"original-context.json": context_text,
                              "original-trace.jsonl": trace_text,
                              "original-source-receipt.json": json.dumps(receipt, sort_keys=True) + "\n"})
        generator = HERE / "diagnostics" / (suffix + "-generator.json")
        write(generator, spec, compact=True)
        recipe = {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-input.json",
            "source": "runtime/fixtures/example.json", "sha256": sha(EXAMPLE)}],
            "generator": {"source": str(generator.relative_to(ROOT)),
                          "sha256": sha(generator)}}
        recipe_path = HERE / "diagnostics" / (suffix + "-recipe.json")
        write(recipe_path, recipe)
        requirements = []
        for index, output_key, method in METHODS:
            if case["case_id"] not in dispositions[index]["case_ids"]:
                continue
            requirements.append({"disposition_index": index,
                                 "requirement": dispositions[index]["requirement"],
                                 "source": dispositions[index]["source"],
                                 "output_key": output_key, "method": method,
                                 "value_type": "object", "kind": "measured",
                                 "inputs": ["original-context.json", "original-trace.jsonl",
                                            "original-source-receipt.json"]})
        contract = {"format": "worker-measurement-contract",
                    "case_id": case["case_id"], "requirements": requirements,
                    "negative": {"remove": ["original-trace.jsonl"],
                                 "error_contains": "Missing required source: original-trace.jsonl"}}
        contract_path = HERE / "diagnostics" / (suffix + "-measurement-contract.json")
        write(contract_path, contract)
        entry["fixture_recipe"] = str(recipe_path.relative_to(ROOT))
        entry["measurement_contract"] = str(contract_path.relative_to(HERE))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py",
                                          "method": "source-sealed full-body overtaking observation"}
    write(MANIFEST, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("case-specific diagnostics:", build())
