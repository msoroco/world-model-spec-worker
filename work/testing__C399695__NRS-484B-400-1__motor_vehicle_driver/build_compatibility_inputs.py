"""Generate five source-shaped synthetic diagnostics for current-runtime proofs."""

import hashlib
import json
from pathlib import Path

from package_spec import AID
from turn_position import measure


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"
EXAMPLE = ROOT / "runtime/fixtures/example.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value, compact=False):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
                               **({"separators": (",", ":")} if compact else {"indent": 2})) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic exceeds 2 MiB")


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads(MANIFEST.read_text())
    base = json.loads(EXAMPLE.read_text())
    mapping = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines()]
    trace = [json.loads(line) for line in base["files"]["trace.jsonl"].splitlines()]
    if len(mapping) != len(trace) or len(mapping) < 9:
        raise ValueError("source-shaped nine-frame diagnostic needed")
    for entry, case in zip(manifest["cases"], plan["cases"]):
        suffix = case["case_id"].removeprefix(AID + "__")
        fixture = json.loads(json.dumps(base))
        qualified = case["qualifying_right_turn_lane"]
        approach = -1 if case["approach_lane_request"] == "turn" else -2
        turn = -1 if case["turn_lane_request"] == "turn" else -2
        site = {"source_id": "synthetic-site", "map_sha256": "b" * 64,
                "public_highway_source": "synthetic-highway",
                "intersection_source": "synthetic-junction",
                "right_lane_design_source": "synthetic-lane-design",
                "qualification_223_4_source": "synthetic-reviewed-223-4",
                "connected_right_exit_source": "synthetic-connected-exit",
                "driver_identity_source": "synthetic-driver", "driver_id": "driver",
                "entry_road_id": 1, "right_exit_road_id": 2, "junction_id": 3,
                "turn_lane_id": -1, "extreme_right_lane_id": -2,
                "public_highway": True, "non_alley_intersection": True,
                "t_intersection": True, "connected_right_exit": True,
                "right_turn_lane_qualified_under_223_4": qualified}
        intention = {"maneuver": "right_turn", "source_ref": "synthetic-pre-approach-intention",
                     "declared_before_frame": mapping[0]["carla_frame"] - 1}
        rows, original = [], []
        for i, mapped in enumerate(mapping):
            phase = "approach" if i < 4 else "right_turn" if i < 7 else "departure"
            road = 1 if i < 7 else 2
            lane = approach if phase == "approach" else turn if phase == "right_turn" else turn
            row = {"frame": i, "native_frame": mapped["carla_frame"],
                   "original_frame": mapped["carla_frame"], "time_s": mapped["time_s"],
                   "actor_ids": ["synthetic-vehicle"], "driver_id": "driver",
                   "lane_id": lane, "road_id": road,
                   "junction_id": 3 if phase == "right_turn" else None,
                   "phase": phase, "source_ref": "synthetic-original-lane-frame",
                   "position_xyz_m": trace[i]["position_m"],
                   "heading_deg": trace[i]["heading_deg"], "speed_mps": trace[i]["speed_mps"],
                   "control": {"throttle": .2, "brake": 0, "steer": .1}}
            rows.append(row)
            original.append({key: row[key] for key in
                             ("original_frame", "time_s", "driver_id", "road_id", "lane_id",
                              "junction_id", "phase", "source_ref", "position_xyz_m")})
        history = {"source_kind": "synthetic_diagnostic_fixture", "assignment_id": AID,
                   "case_id": case["case_id"], "reviewed_site_sha256": "a" * 64,
                   "ego_actor_id": "synthetic-vehicle", "driver_actor_id": "driver",
                   **{key: value for key, value in site.items() if key not in ("source_id", "driver_id")},
                   "intended_maneuver": intention, "samples": rows}
        history_text = json.dumps(history, sort_keys=True) + "\n"
        measurement_text = json.dumps(measure(site, original, intention), sort_keys=True) + "\n"
        frame_rows = [{**mapped, "video_frame": i, "native_frame": mapped["carla_frame"]}
                      for i, mapped in enumerate(mapping)]
        frame_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_rows)
        trace_text = base["files"]["trace.jsonl"]
        digest = lambda raw: hashlib.sha256(raw.encode()).hexdigest()
        receipt = {"source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
                   "case_id": case["case_id"], "history_sha256": digest(history_text),
                   "measurement_sha256": digest(measurement_text),
                   "trace_sha256": digest(trace_text), "frame_map_sha256": digest(frame_text),
                   "physical_acceptance": False, "legal_verdict": None}
        fixture["files"].update({"turn-position-history.json": history_text,
                                 "turn-position-measurement.json": measurement_text,
                                 "trace.jsonl": trace_text, "video_frames.jsonl": frame_text,
                                 "original-source-receipt.json": json.dumps(receipt, sort_keys=True) + "\n"})
        generator = HERE / "diagnostics" / (suffix + "-generator.json")
        put(generator, fixture, compact=True)
        recipe = HERE / "diagnostics" / (suffix + "-recipe.json")
        put(recipe, {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-input.json", "source": "runtime/fixtures/example.json",
            "sha256": sha(EXAMPLE)}], "generator": {
                "source": str(generator.relative_to(ROOT)), "sha256": sha(generator)}})
        keys = ("driver_and_intention", "conditional_lane_qualification",
                "approach_lane_position", "turn_lane_position", "extreme_right_alternative")
        requirements = [{"disposition_index": disposition["disposition_index"],
                         "requirement": disposition["requirement"], "source": disposition["source"],
                         "output_key": keys[disposition["disposition_index"]],
                         "method": "source_sealed_turn_position", "value_type": "object",
                         "kind": "measured", "inputs": ["turn-position-history.json",
                                                            "original-source-receipt.json", "trace.jsonl"]}
                        for disposition in plan["requirement_dispositions"]
                        if case["case_id"] in disposition["case_ids"]]
        contract = HERE / "diagnostics" / (suffix + "-measurement-contract.json")
        put(contract, {"format": "worker-measurement-contract", "case_id": case["case_id"],
                       "requirements": requirements,
                       "negative": {"remove": ["turn-position-history.json"],
                                    "error_contains": "Missing required source: turn-position-history.json"}})
        entry["fixture_recipe"] = str(recipe.relative_to(ROOT))
        entry["measurement_contract"] = str(contract.relative_to(HERE))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py",
                                          "method": "source-sealed original Native approach, turn and lane-design review"}
    put(MANIFEST, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("source-shaped diagnostics:", build())
