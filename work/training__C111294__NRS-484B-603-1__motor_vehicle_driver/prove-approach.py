"""Synthetic CPU proof for the saved intersection-approach measurement path."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("measure_approach", ROOT / "native" / "measure_approach.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FIXTURES = ROOT / "draft-fixtures"


def make_trace(profile: str) -> bytes:
    y = -120.0
    lines = []
    for i in range(module.FRAMES):
        if profile == "decrease":
            mph = 30.0 if y < -60 else 20.0 if y >= -20 else 20.0 + (-20-y)/4
        elif profile == "hold":
            mph = 30.0
        else:
            raise ValueError(profile)
        speed = mph * .44704
        y += speed/module.FPS
        lines.append(json.dumps({"frame": i, "t_s": i/module.FPS,
            "ego_actor_id": 101, "other_actor_id": 202,
            "ego_role": "motor_vehicle_driver", "other_role": "motor_vehicle_driver",
            "ego_position_m": [1.75, y, 0], "other_position_m": [-30+5*i/module.FPS, 1.75, 0],
            "ego_velocity_mps": [0, speed, 0], "source_kind": "synthetic_cpu_fixture"},
            sort_keys=True))
    return ("\n".join(lines)+"\n").encode()


def run() -> dict:
    FIXTURES.mkdir(exist_ok=True)
    results = {}
    for profile, relation in (("decrease", "measured_early_decrease_held"),
                              ("hold", "measured_no_material_decrease")):
        raw = make_trace(profile)
        path = FIXTURES / f"{profile}-synthetic-native.jsonl"
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        measurement = module.measure(path, digest)
        if measurement["measured_relation"] != relation:
            raise AssertionError((profile, measurement))
        results[profile] = measurement
        try:
            module.measure(path, "0"*64)
        except ValueError as exc:
            if str(exc) != "Saved Native source hash changed":
                raise
        else:
            raise AssertionError("Changed source hash accepted")
    reflected_rows = [json.loads(x) for x in make_trace("decrease").splitlines()]
    for row in reflected_rows:
        row["ego_position_m"][1] *= -1
        row["ego_velocity_mps"][1] *= -1
    reflected = ("\n".join(json.dumps(row, sort_keys=True) for row in reflected_rows)+"\n").encode()
    reflected_path = FIXTURES/"decrease-reflected-synthetic-native.jsonl"
    reflected_path.write_bytes(reflected)
    reflected_measurement = module.measure(reflected_path, hashlib.sha256(reflected).hexdigest())
    if (reflected_measurement["measured_relation"] != "measured_early_decrease_held" or
            reflected_measurement["measured_travel_direction_y"] != -1):
        raise AssertionError("Reflected Native coordinate path changed result")
    results["decrease_reflected"] = reflected_measurement
    altered_rows = [dict(row) for row in reflected_rows]
    altered_rows[10] = dict(altered_rows[10])
    altered_rows[10]["ego_velocity_mps"] = [0, 0, 0]
    altered = ("\n".join(json.dumps(row, sort_keys=True) for row in altered_rows)+"\n").encode()
    altered_path = FIXTURES/"velocity-mismatch-negative.jsonl"
    altered_path.write_bytes(altered)
    try:
        module.measure(altered_path, hashlib.sha256(altered).hexdigest())
    except ValueError as exc:
        if str(exc) != "Saved pose and speed disagree":
            raise
    else:
        raise AssertionError("Pose/velocity disagreement accepted")
    altered_path.unlink()
    # A validly hashed trace with a missing frame must also fail.
    truncated = FIXTURES / "truncated-negative.jsonl"
    truncated.write_bytes(make_trace("decrease").split(b"\n", 1)[1])
    try:
        module.measure(truncated, hashlib.sha256(truncated.read_bytes()).hexdigest())
    except ValueError as exc:
        if str(exc) != "Expected 480 complete Native frames":
            raise
    else:
        raise AssertionError("Missing frame accepted")
    truncated.unlink()
    return {"passed": True, "source_scope": "synthetic CPU Native-shaped fixtures",
            "law_id": "NRS-484B-603-1", "cell_id": "C111294",
            "positives": results, "negatives": ["changed source hash", "missing frame", "pose/velocity disagreement"],
            "physical_behavior_observed": False, "original_pixels_observed": False}


if __name__ == "__main__":
    result = run()
    (ROOT / "approach-proof.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, sort_keys=True))
