"""Add the source law's other-traffic yield comparison to the worker plan."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATH = HERE / "case-plan.json"
PAIR = ("traffic_yield_wait", "traffic_conflict_entry")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads(PATH.read_text())
    existing = {row["case_id"].removeprefix(HERE.name + "__"): row
                for row in plan["cases"]}
    if any(suffix in existing for suffix in PAIR):
        if not all(suffix in existing for suffix in PAIR):
            raise ValueError("Partial traffic pair in case plan")
        return {"cases": len(plan["cases"]), "comparisons": len(plan["comparisons"]),
                "plan_sha256": sha(PATH), "already_present": True}
    if len(existing) != 8 or len(plan["comparisons"]) != 4:
        raise ValueError("Expected reviewed eight-case starting plan")
    for suffix, source in zip(PAIR, ("yield_wait", "yield_conflict_entry")):
        case = deepcopy(existing[source])
        case["case_id"] = HERE.name + "__" + suffix
        case["comparison_variable"] = "signal_directed_other_traffic_response"
        case["comparison_unit"] = "observed_ego_and_other_traffic_full_body_conflict"
        case["requested_setting"] = suffix
        case["case_description"] = (
            "After the same red-signal full-body stop, compare waiting for signal-directed "
            "cross traffic with a deliberate occupied-lane entry probe. Original traffic "
            "direction and legal right-of-way remain unresolved.")
        case["fixed_context"] = (
            "Hold marked-reference road, extreme-right right-turn route, separate green "
            "west-approach signal, other-traffic actor path, early-cleared pedestrian path, "
            "weather, capture profile and all noncompared controller knobs constant.")
        plan["cases"].append(case)
    plan["comparisons"].append({
        "comparison_id": HERE.name + "__comparison_other_traffic_yield",
        "case_ids": [HERE.name + "__" + suffix for suffix in PAIR],
        "deliberate_differences": ["signal_directed_other_traffic_response"],
        "fixed_conditions": ["cell", "actor", "steady_red_ego_signal",
                             "marked_stop_reference", "extreme_right_approach",
                             "two_directional_receiving_road",
                             "separate_green_cross_traffic_signal",
                             "other_traffic_path", "early_cleared_pedestrian_path",
                             "weather", "noncompared_controller_settings",
                             "camera_and_capture_profile"],
        "status": "planned_unverified"})
    ids = [HERE.name + "__" + suffix for suffix in PAIR]
    for index in (0, 2, 3):
        plan["requirement_dispositions"][index]["case_ids"].extend(ids)
    plan["runtime_uncertainties"].append(
        "Other-traffic pair has an authored separate green signal and moving west-approach "
        "vehicle; original Native lane direction, movement, full-body overlap, pixels and "
        "legal yielding remain unverified. CPU diagnostic recipes are synthetic.")
    PATH.write_text(json.dumps(plan, indent=2) + "\n")
    return {"cases": 10, "comparisons": 5, "plan_sha256": sha(PATH),
            "already_present": False}


if __name__ == "__main__":
    print(json.dumps(main()))
