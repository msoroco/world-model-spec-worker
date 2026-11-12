"""Source-hash bound CPU contrast of current and proposed approach policies."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decide(policy, distance, speed, *, inside=False):
    return policy.step(distance_to_hold_m=1.0, ego_speed_mps=0.0,
                       oncoming_distance_to_conflict_m=distance,
                       oncoming_closing_speed_mps=speed,
                       oncoming_in_intersection=inside,
                       oncoming_cleared=False, turn_complete=False)


def run(folder):
    current = load(folder / "controller.py", "current_hazard_controller")
    proposed = load(folder / "hazard_sweep_policy.py", "proposed_hazard_controller")
    config = json.loads((folder / "config.json").read_text())
    threshold = config["controller_release_ttc_s"]
    rows = []
    for distance in (4.0, 8.0, 12.0, 16.0, 24.0):
        for speed in (2.0, 4.0, 6.0):
            kwargs = {"release_ttc_s": threshold,
                      "approach_speed_mps": config["approach_speed_mps"]}
            old = decide(current.LeftTurnController(**kwargs), distance, speed)
            new = decide(proposed.HazardSweepPolicy(**kwargs), distance, speed)
            ttc = distance / speed
            assert old["state"] == "yield"
            assert new["state"] == ("yield" if ttc < threshold else "turn")
            rows.append({"distance_m": distance, "closing_speed_mps": speed,
                         "ttc_s": ttc, "current_state": old["state"],
                         "candidate_state": new["state"]})
    kwargs = {"release_ttc_s": threshold,
              "approach_speed_mps": config["approach_speed_mps"]}
    inside = decide(proposed.HazardSweepPolicy(**kwargs), 24.0, 2.0, inside=True)
    assert inside["state"] == "yield" and inside["brake"] == 1.0
    assert sum(row["candidate_state"] == "yield" for row in rows) > 0
    assert sum(row["candidate_state"] == "turn" for row in rows) > 0
    return {"format": "worker-hazard-sweep-policy-cpu-proof",
            "current_controller_sha256": sha(folder / "controller.py"),
            "candidate_policy_sha256": sha(folder / "hazard_sweep_policy.py"),
            "config_sha256": sha(folder / "config.json"),
            "engineering_release_ttc_s": threshold,
            "samples": rows, "occupied_junction_state": inside["state"],
            "canonical_construction_integrated": False,
            "exact_offline_compatibility_saved_proved": False,
            "native_feasibility_proven": False,
            "legal_hazard_cutoff_asserted": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parent)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("samples", len(result["samples"]))
    print("candidate yield", sum(r["candidate_state"] == "yield" for r in result["samples"]))
    print("candidate turn", sum(r["candidate_state"] == "turn" for r in result["samples"]))
    print("occupied junction", result["occupied_junction_state"])


if __name__ == "__main__":
    main()
