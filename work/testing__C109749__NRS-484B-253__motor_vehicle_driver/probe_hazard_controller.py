"""Probe the authored controller's engineering response to approaching traffic.

This is a CPU control diagnostic, not a Native trajectory or legal hazard test.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(folder):
    spec = importlib.util.spec_from_file_location("hazard_probe_controller", folder / "controller.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config_path = folder / "config.json"
    config = json.loads(config_path.read_text())
    release = config["controller_release_ttc_s"]
    rows = []
    for distance in (4.0, 8.0, 12.0, 16.0, 24.0):
        for speed in (2.0, 4.0, 6.0):
            controller = module.LeftTurnController(
                release_ttc_s=release,
                approach_speed_mps=config["approach_speed_mps"],
            )
            output = controller.step(
                distance_to_hold_m=1.0,
                ego_speed_mps=0.0,
                oncoming_distance_to_conflict_m=distance,
                oncoming_closing_speed_mps=speed,
                oncoming_in_intersection=False,
                oncoming_cleared=False,
                turn_complete=False,
            )
            rows.append({"distance_m": distance, "closing_speed_mps": speed,
                         "ttc_s": distance / speed, "state": output["state"],
                         "brake": output["brake"], "throttle": output["throttle"]})
    below = [row for row in rows if row["ttc_s"] < release]
    above = [row for row in rows if row["ttc_s"] >= release]
    assert below and above, "Probe does not straddle engineering release time"
    assert all(row["state"] == "yield" and row["brake"] == 1.0 for row in rows)
    return {
        "format": "worker-hazard-controller-probe",
        "controller_sha256": digest(folder / "controller.py"),
        "config_sha256": digest(config_path),
        "engineering_release_ttc_s": release,
        "samples": rows,
        "below_release_count": len(below),
        "at_or_above_release_count": len(above),
        "observed_constraint": "At the hold position, every sampled approach remains in yield until the oncoming_cleared input becomes true, including distances at or above the engineering TTC release setting.",
        "next_construction_action": "Author distinct source-bound approaching-body histories and a policy that can express yield versus turn when no opposing body has entered, then rerun affected exact and fallback proofs.",
        "native_feasibility_proven": False,
        "legal_hazard_cutoff_asserted": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    result = run(folder)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("samples", len(result["samples"]))
    print("below", result["below_release_count"], "at_or_above", result["at_or_above_release_count"])
    print(result["observed_constraint"])


if __name__ == "__main__":
    main()
