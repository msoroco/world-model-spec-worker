"""Build case-specific synthetic right-pass diagnostics and source contracts."""

import hashlib
import json
from pathlib import Path

from package_spec import AID

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
    trace_text = base["files"]["trace.jsonl"]
    frames = [{**mapped, "video_frame": i, "native_frame": mapped["carla_frame"]}
              for i, mapped in enumerate(mapping)]
    frame_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in frames)
    if len(mapping) != 9:
        raise ValueError("pinned diagnostic frame count changed")
    paths = ([0, 2, 4, 6, 9, 11, 14, 16, 18] if len(mapping) == 9 else [])
    for entry, case in zip(manifest["cases"], plan["cases"]):
        suffix = case["case_id"].removeprefix(AID + "__")
        fixture = json.loads(json.dumps(base))
        target = [7.0, 9.0] if suffix == "close_gap" else [10.0, 12.0]
        ids = ["diagnostic-ego", "diagnostic-target"]
        if suffix == "cross_traffic":
            ids.append("diagnostic-crossing")
        rows = []
        for i, mapped in enumerate(mapping):
            station = paths[i]
            row = {"frame": i, "native_frame": mapped["carla_frame"],
                   "time_s": mapped["time_s"], "actor_ids": ids,
                   "ego_body_s_bounds_m": [float(station), float(station + 2)],
                   "target_body_s_bounds_m": target,
                   "ego_body_y_bounds_m": [-2.0, -1.0],
                   "target_body_y_bounds_m": [0.0, 1.0],
                   "paved_y_bounds_m": [-4.0, 4.0],
                   "ego_speed_mps": 5.0, "target_speed_mps": 3.0,
                   "ego_control": {"throttle": .25, "brake": 0, "steer": 0}}
            if len(ids) == 3:
                row.update(conflict_body_s_bounds_m=[15.0, 17.0],
                           conflict_body_y_bounds_m=[-0.5, 0.5])
            rows.append(row)
        history = {"source_kind": "original_native_actor_history",
                   "assignment_id": AID, "case_id": case["case_id"],
                   "variant": suffix, "map_source_kind": "original_native_map_geometry",
                   "map_sha256": "a" * 64, "camera_profile": "overview1080-capability",
                   "reviewed_site_sha256": "b" * 64, "driver_actor_id": "diagnostic-driver",
                   "right_lane_same_direction": True,
                   "paved_boundary_source": "synthetic diagnostic pavement",
                   "actor_ids": ids, "samples": rows}
        history_text = json.dumps(history, sort_keys=True) + "\n"
        receipt = {"source_kind": "synthetic_diagnostic_fixture",
                   "diagnostic_fixture": True, "case_id": case["case_id"],
                   "history_sha256": hashlib.sha256(history_text.encode()).hexdigest(),
                   "trace_sha256": hashlib.sha256(trace_text.encode()).hexdigest(),
                   "frame_map_sha256": hashlib.sha256(frame_text.encode()).hexdigest(),
                   "physical_acceptance": False, "legal_verdict": None}
        fixture["files"].update({"right-pass-history.json": history_text,
                                 "trace.jsonl": trace_text,
                                 "video_frames.jsonl": frame_text,
                                 "original-source-receipt.json": json.dumps(receipt, sort_keys=True) + "\n"})
        generator = HERE / "diagnostics" / (suffix + "-generator.json")
        put(generator, fixture, compact=True)
        recipe = HERE / "diagnostics" / (suffix + "-recipe.json")
        put(recipe, {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-input.json", "source": "runtime/fixtures/example.json",
            "sha256": sha(EXAMPLE)}], "generator": {
                "source": str(generator.relative_to(ROOT)), "sha256": sha(generator)}})
        keys = ("whole_right_pass", "approach_space")
        requirements = [{"disposition_index": d["disposition_index"],
                         "requirement": d["requirement"], "source": d["source"],
                         "output_key": keys[d["disposition_index"]],
                         "method": "source_sealed_right_pass_measurement", "value_type": "object",
                         "kind": "measured", "inputs": ["right-pass-history.json",
                                                     "original-source-receipt.json", "trace.jsonl"]}
                        for d in plan["requirement_dispositions"]]
        contract = HERE / "diagnostics" / (suffix + "-measurement-contract.json")
        put(contract, {"format": "worker-measurement-contract", "case_id": case["case_id"],
                       "requirements": requirements,
                       "negative": {"remove": ["right-pass-history.json"],
                                    "error_contains": "Missing required source: right-pass-history.json"}})
        entry["fixture_recipe"] = str(recipe.relative_to(ROOT))
        entry["measurement_contract"] = str(contract.relative_to(HERE))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py",
                                          "method": "source-sealed original right-pass body and motion readback"}
    put(MANIFEST, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("right-pass compatibility inputs:", build())
