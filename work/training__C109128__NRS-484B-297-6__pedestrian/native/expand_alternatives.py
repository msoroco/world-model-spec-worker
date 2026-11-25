"""Complete exact statutory alternative case planning without legal cutoffs."""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent


def expand():
    target = FOLDER / "case-plan.json"
    plan = json.loads(target.read_text())
    base = plan["cases"][:2]
    if [case["case_id"].rsplit("__", 1)[-1] for case in base] != ["condition_a", "condition_b"]:
        raise ValueError("frozen witness pair changed")
    pairs = (("direction_east", "direction_west", "sidewalk_travel_direction",
              "NRS 484B.297(6)(b) continued sidewalk direction regardless of traffic direction"),
             ("bike_passable", "bike_impassable", "intervening_area_passability",
              "NRS 484B.297(6)(c) bicycle-lane permission conditional on intervening area impassability"))
    for first, second, variable, phrase in pairs:
        members = []
        for index, condition in enumerate((first, second)):
            case = copy.deepcopy(base[index])
            case["case_id"] = FOLDER.name + "__" + condition
            case["source_branch"] = phrase
            case["comparison_variable"] = variable
            case["condition_index"] = index
            case["claim"] = "CPU Native request and source measurement only; physical and legal review pending"
            members.append(case)
        existing = {case["case_id"]: case for case in plan["cases"]}
        for case in members:
            existing[case["case_id"]] = case
        plan["cases"] = list(existing.values())
        comparison = copy.deepcopy(plan["comparisons"][0])
        comparison["comparison_id"] = FOLDER.name + "__" + variable + "__comparison"
        comparison["case_ids"] = [case["case_id"] for case in members]
        comparison["deliberate_differences"] = [variable]
        comparison["status"] = "cpu_native_request_and_diagnostic_source_pair"
        comparison["audit_gap"] = "Original Native and physical source review pending"
        if not any(row["comparison_id"] == comparison["comparison_id"] for row in plan["comparisons"]):
            plan["comparisons"].append(comparison)
    by_suffix = {case["case_id"].rsplit("__", 1)[-1]: case["case_id"] for case in plan["cases"]}
    for index, disposition in enumerate(plan["requirement_dispositions"]):
        disposition["status"] = "selected_required"
        if index == 3:
            disposition["case_ids"] = [by_suffix["direction_east"], by_suffix["direction_west"]]
        elif index == 4:
            disposition["case_ids"] = [by_suffix["bike_passable"], by_suffix["bike_impassable"]]
        elif index != 6:
            disposition["case_ids"] = list(by_suffix.values())
        else:
            disposition["case_ids"] = [by_suffix["condition_a"], by_suffix["condition_b"]]
        disposition["evidence_or_gap"] = (
            "Exact selected case source, Native construction and diagnostic source measurements bound; "
            "original physical feasibility, due care, passability, near-side possibility, "
            "and first practicable return remain for independent review.")
    term_channel = {"ru.subject": "ru.subject", "st.sidewalk": "st.sidewalk",
        "st.obstruction": "st.obstruction", "st.highway": "st.highway",
        "rel.occupies": "rel.occupies", "st.road_edge": "st.road_edge",
        "kin.heading": "kin.heading", "st.bicycle_lane_or_path": "st.bicycle_lane_or_path",
        "kin.path_length": "kin.path_length", "drv.time_to_conflict": "drv.time_to_conflict"}
    for term, item in plan["source_observation_mapping"].items():
        if term not in term_channel:
            raise ValueError("unmapped frozen source observation term: " + term)
        item["channels"] = [term_channel[term]]
        item["evidence"] = (
            "Original Native map/body/frame source channel; source availability and "
            "physical meaning are independently reviewed. No legal threshold inferred.")
    target.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"cases": len(plan["cases"]),
                      "comparisons": len(plan["comparisons"]),
                      "selected_requirements": len(plan["requirement_dispositions"])}))


if __name__ == "__main__":
    expand()
