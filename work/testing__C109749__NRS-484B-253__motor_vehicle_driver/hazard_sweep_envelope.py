"""CPU envelope for an engineering TTC control sweep, without legal labels."""
import hashlib
import importlib.util
import json
from pathlib import Path


SETPOINTS_S = (3.0, 4.0, 5.0)
DISTANCES_M = (8.0, 12.0, 16.0, 20.0, 24.0)
CLOSING_SPEED_MPS = 4.0


def load_policy(path):
    spec = importlib.util.spec_from_file_location("candidate_hazard_sweep_policy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HazardSweepPolicy


def probe(policy_type, release_s, distance_m, *, inside=False):
    policy = policy_type(release_ttc_s=release_s, approach_speed_mps=3.0)
    return policy.step(distance_to_hold_m=1.0, ego_speed_mps=0.0,
                       oncoming_distance_to_conflict_m=distance_m,
                       oncoming_closing_speed_mps=CLOSING_SPEED_MPS,
                       oncoming_in_intersection=inside,
                       oncoming_cleared=False, turn_complete=False)["state"]


def evaluate(folder):
    source = Path(folder) / "hazard_sweep_policy.py"
    policy_type = load_policy(source)
    rows = []
    for distance_m in DISTANCES_M:
        decisions = {str(release_s): probe(policy_type, release_s, distance_m)
                     for release_s in SETPOINTS_S}
        rows.append({"distance_to_conflict_m": distance_m,
                     "closing_speed_mps": CLOSING_SPEED_MPS,
                     "measured_ttc_s": distance_m / CLOSING_SPEED_MPS,
                     "states_by_control_setpoint": decisions})
    patterns = {release_s: tuple(row["states_by_control_setpoint"][str(release_s)]
                                 for row in rows) for release_s in SETPOINTS_S}
    if len(set(patterns.values())) != len(SETPOINTS_S):
        raise ValueError("Engineering setpoints do not separate controller responses")
    if any(probe(policy_type, release_s, 24.0, inside=True) != "yield"
           for release_s in SETPOINTS_S):
        raise ValueError("Occupied intersection must preserve yielding response")
    return {"format": "worker-hazard-control-sweep-envelope",
            "policy_source": "hazard_sweep_policy.py",
            "policy_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "release_ttc_setpoints_s": SETPOINTS_S,
            "fixed_closing_speed_mps": CLOSING_SPEED_MPS,
            "rows": rows,
            "distinct_control_patterns": True,
            "occupied_intersection_yields": True,
            "canonical_construction_integrated": False,
            "exact_saved_processing_proved": False,
            "native_feasibility_proven": False,
            "legal_hazard_cutoff_asserted": False}


def main():
    folder = Path(__file__).resolve().parent
    result = evaluate(folder)
    (folder / "hazard-sweep-envelope.json").write_text(json.dumps(result, indent=2) + "\n")
    print("three distinct engineering control response patterns")


if __name__ == "__main__":
    main()
