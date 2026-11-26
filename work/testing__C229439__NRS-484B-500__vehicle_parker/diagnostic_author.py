"""Author case-specific textual CPU diagnostics; these are never recordings."""

import hashlib
import json
from pathlib import Path

from comparison_audit import CASES
from parking_place import ASSIGNMENT


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n",
                    encoding="utf-8")


def author():
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text(encoding="utf-8"))
    mapping = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines() if line]
    for suffix, (conduct, footprint, context_kind) in CASES.items():
        case_id = ASSIGNMENT + "__" + suffix
        spec = json.loads(json.dumps(base))
        for unrelated in ("alley_context.json", "body_history.jsonl", "speed_samples.jsonl"):
            spec["files"].pop(unrelated, None)
        zone = [[95, -2], [105, -2], [105, 5], [95, 5]]
        target_x = 100 if footprint == "inside" else 115
        context = {"assignment_id": ASSIGNMENT, "case_id": case_id,
                   "map_id": "synthetic-parking-map", "device_id": "synthetic-device",
                   "designated_place_id": "synthetic-place",
                   "designated_place_polygon": zone, "device_erected": True,
                   "device_actor_id": 300, "vehicle_actor_id": 205, "parker_actor_id": 205,
                   "curb_person_actor_id": 410, "curb_person_blueprint": "synthetic-walker",
                   "official_authority_source": "synthetic-authority-packet",
                   "device_instructions_source": "synthetic-device-packet",
                   "hazard_or_congestion_source": "synthetic-place-facts",
                   "hazard_or_congestion_status": context_kind,
                   "loading_activity_source": "synthetic-loading-observation",
                   "officer_or_device_direction_source": "synthetic-direction-observation",
                   "place_feature": "traffic_queue" if context_kind == "congested" else "curve"}
        history = []
        for i, video in enumerate(mapping):
            x = target_x - max(0, 6 - i)
            history.append({"frame": video["carla_frame"], "time_s": video["time_s"],
                            "vehicle_footprint": [[x - 2, 0], [x + 2, 0],
                                                  [x + 2, 3], [x - 2, 3]],
                            "speed_mps": 0 if i >= 6 else 3,
                            "position_m": [x, 1.5], "vehicle_actor_id": 205,
                            "device_actor_id": 300,
                            "curb_person_actor_id": 410,
                            "curb_person_position_m": [target_x, 6],
                            "curb_person_body_m": [[target_x - .25, 5.75],
                                                   [target_x + .25, 5.75],
                                                   [target_x + .25, 6.25],
                                                   [target_x - .25, 6.25]],
                            "control_command": {"throttle": 0, "brake": 1 if i >= 6 else 0.65,
                                                "hand_brake": conduct == "park" and i >= 6},
                            "phase": "hold" if i >= 6 else "approach",
                            "requested_conduct": conduct,
                            "loading_activity_observed": None,
                            "officer_direction_observed": None})
        files = spec["files"]
        files["parking-context.json"] = json.dumps(context, allow_nan=False) + "\n"
        files["parking-history.jsonl"] = "".join(json.dumps(row, allow_nan=False) + "\n" for row in history)
        acquisition = {name: {"kind": "original_native", "sha256": sha(files[name])}
                       for name in ("parking-context.json", "parking-history.jsonl",
                                    "video_frames.jsonl", "trace.jsonl")}
        files["acquisition.json"] = json.dumps(acquisition, allow_nan=False) + "\n"
        files["fixture-provenance.json"] = json.dumps({"scope": "Case-specific synthetic parking measurement with generic Native-shaped adapter graph; no physical recording or legal status.",
                                                       "frames": len(mapping)}, allow_nan=False) + "\n"
        output = ROOT / ("diagnostic-" + suffix + ".json")
        write(output, spec)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        recipe = {"format": "worker-fixture-recipe", "sources": [
            {"path": "diagnostic-input.json", "source": str(output.relative_to(REPO)),
             "sha256": digest}],
            "generator": {"source": str(output.relative_to(REPO)), "sha256": digest}}
        write(ROOT / ("diagnostic-" + suffix + "-recipe.json"), recipe)


if __name__ == "__main__":
    author()
