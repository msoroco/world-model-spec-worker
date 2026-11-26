"""Build source-shaped synthetic right-turn-lane diagnostics for saved-only checks."""

import hashlib
import json
from pathlib import Path

from package_spec import AID
from right_turn_lane_probe import measure

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
    for entry, case in zip(manifest["cases"], plan["cases"]):
        suffix = case["case_id"].removeprefix(AID + "__")
        fixture = json.loads(json.dumps(base))
        route = case["requested_departure_route"]
        purpose = case["declared_maneuver_purpose"]
        site = {"highway_source": "synthetic-highway", "turn_lane_id": -1,
                "turn_lane_source": "synthetic-lane", "one_right_turn_lane": True,
                "exclusive_right_turn": True, "t_junction_id": 3,
                "entry_road_id": 1, "right_exit_road_id": 2,
                "connected_route_source": "synthetic-connected-route", "ego_id": "driver"}
        declaration = {"declared_purpose": purpose, "source_ref": "synthetic-purpose",
                       "declared_before_frame": mapping[0]["carla_frame"] - 1}
        rows, frames = [], []
        for i, mapped in enumerate(mapping):
            road = 1 if i < 6 else (2 if route == "right_turn" else 4)
            lane = -1 if i < 6 else -2
            maneuver = "right_turn" if road == 2 else "other"
            row = {"frame": i, "native_frame": mapped["carla_frame"],
                   "original_frame": mapped["carla_frame"], "time_s": mapped["time_s"],
                   "actor_ids": ["synthetic-vehicle"], "driver_id": "driver",
                   "lane_id": lane, "road_id": road, "junction_id": 3 if i >= 6 else None,
                   "maneuver": maneuver, "source_ref": "synthetic-site",
                   "position_xyz_m": trace[i]["position_m"],
                   "heading_deg": trace[i]["heading_deg"], "speed_mps": trace[i]["speed_mps"],
                   "control": {"throttle": .2, "brake": 0, "steer": .1}}
            rows.append(row)
            frames.append({"original_frame": row["original_frame"], "time_s": row["time_s"],
                           "lane_id": lane, "road_id": road, "maneuver": maneuver,
                           "source_ref": row["source_ref"], "driver_id": row["driver_id"]})
        history = {"source_kind": "synthetic_diagnostic_fixture", "assignment_id": AID,
                   "case_id": case["case_id"], "reviewed_site_sha256": "a" * 64,
                   "map_sha256": "b" * 64,
                   "highway_source": site["highway_source"], "turn_lane_source": site["turn_lane_source"],
                   "connected_route_source": site["connected_route_source"],
                   "driver_actor_id": "driver", "ego_actor_id": "synthetic-vehicle",
                   "public_highway": True, "one_right_turn_lane": True, "exclusive_right_turn": True,
                   "t_junction_id": 3, "turn_lane_id": -1, "entry_road_id": 1,
                   "right_exit_road_id": 2, "purpose_declaration": declaration,
                   "requested_departure_route": route, "actor_ids": ["synthetic-vehicle"],
                   "samples": rows}
        history_text = json.dumps(history, sort_keys=True) + "\n"
        measurement_text = json.dumps(measure(site, frames, declaration), sort_keys=True) + "\n"
        trace_text = base["files"]["trace.jsonl"]
        frame_rows = [{**mapped, "video_frame": i, "native_frame": mapped["carla_frame"]}
                      for i, mapped in enumerate(mapping)]
        frame_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_rows)
        receipt = {"source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
                   "case_id": case["case_id"],
                   "history_sha256": hashlib.sha256(history_text.encode()).hexdigest(),
                   "trace_sha256": hashlib.sha256(trace_text.encode()).hexdigest(),
                   "frame_map_sha256": hashlib.sha256(frame_text.encode()).hexdigest(),
                   "measurement_sha256": hashlib.sha256(measurement_text.encode()).hexdigest(),
                   "physical_acceptance": False, "legal_verdict": None}
        fixture["files"].update({"right-turn-history.json": history_text,
                                 "right-turn-measurement.json": measurement_text,
                                 "trace.jsonl": trace_text, "video_frames.jsonl": frame_text,
                                 "original-source-receipt.json": json.dumps(receipt, sort_keys=True) + "\n"})
        generator = HERE / "diagnostics" / (suffix + "-generator.json")
        put(generator, fixture, compact=True)
        recipe = HERE / "diagnostics" / (suffix + "-recipe.json")
        put(recipe, {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-input.json", "source": "runtime/fixtures/example.json",
            "sha256": sha(EXAMPLE)}], "generator": {
                "source": str(generator.relative_to(ROOT)), "sha256": sha(generator)}})
        keys = ("public_highway_and_lane_design", "right_turn_lane_occupancy",
                "declared_maneuver_purpose")
        requirements = [{"disposition_index": d["disposition_index"],
                         "requirement": d["requirement"], "source": d["source"],
                         "output_key": keys[d["disposition_index"]],
                         "method": "source_sealed_right_turn_measurement", "value_type": "object",
                         "kind": "measured", "inputs": ["right-turn-history.json",
                                                      "original-source-receipt.json", "trace.jsonl"]}
                        for d in plan["requirement_dispositions"]]
        contract = HERE / "diagnostics" / (suffix + "-measurement-contract.json")
        put(contract, {"format": "worker-measurement-contract", "case_id": case["case_id"],
                       "requirements": requirements,
                       "negative": {"remove": ["right-turn-history.json"],
                                    "error_contains": "Missing required source: right-turn-history.json"}})
        entry["fixture_recipe"] = str(recipe.relative_to(ROOT))
        entry["measurement_contract"] = str(contract.relative_to(HERE))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py",
                                         "method": "source-sealed Native lane/road and pre-entry purpose readback"}
    put(MANIFEST, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("right-turn-lane compatibility inputs:", build())
