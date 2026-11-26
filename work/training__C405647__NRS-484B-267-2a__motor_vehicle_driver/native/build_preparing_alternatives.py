"""Bind the two statutory preparing-to-move paths to exact source needs."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
AID = FOLDER.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = FOLDER / "case-plan.json"
    common = {
        "law_source": "NRS 484B.267(2)(a) and NRS 484B.267(4)",
        "case_plan_sha256": sha(plan),
        "actor": "motor_vehicle_driver",
        "required_frame_count": 600,
        "required_rate_hz": 20,
        "required_views": ["overview", "approach", "reference_corner", "driver_reference"],
        "required_original_sources": [
            "subject_approach_source_id", "authorized_vehicle_source_id",
            "flashing_equipment_source_id", "flashing_pixel_source_id",
            "flashing_qualification_source_id", "officer_direction_source_id",
            "road_context_source_id", "weather_context_source_id"],
        "status": "prospective_original_source_pending",
        "legal_outcome_claimed": False,
    }
    alternatives = []
    for branch, extra in (
        ("visible_vehicle_movement", ["movement_pixel_source_id"]),
        ("visible_driver_hand_signal", ["hand_signal_pixel_source_id", "hand_signal_actor_source_id"]),
    ):
        alternatives.append({**common,
                             "exact_case_id": AID + "__preparing_to_move__" + branch,
                             "activation_branch": branch,
                             "already_moving": False,
                             "required_branch_sources": extra,
                             "classification_script": "native/branch_alternatives.py",
                             "selected_for_current_pair": False})
    output = FOLDER / "native/preparing-alternative-plan.json"
    output.write_text(json.dumps({"format": "c405647-preparing-alternatives-v1",
                                  "alternatives": alternatives}, indent=2, sort_keys=True) + "\n")
    return {"alternatives": len(alternatives), "sha256": sha(output)}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
