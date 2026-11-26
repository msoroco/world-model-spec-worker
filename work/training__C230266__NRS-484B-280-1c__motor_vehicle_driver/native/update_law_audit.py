"""Bind each textual pedestrian position to its own planned source audit."""

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
ASSIGNMENT = ROOT.name


def sha(data):
    return hashlib.sha256(data).hexdigest()


def store(path, value):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stage = SCRATCH / (path.name + ".staging")
    stage.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    os.replace(stage, path)


def main():
    source_path = REPO / "inputs" / ASSIGNMENT / "assignment.json"
    assignment = json.loads(source_path.read_text())
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    law_text = assignment["law"]["text"]
    if plan["source_law"]["text"] != law_text:
        raise ValueError("Plan differs from frozen exact law")
    mapping = plan["source_observation_mapping"]
    mapping.update({
        "st.bus_stop": {"evidence": "original bus-stop designation, geometry and pedestrian position survey",
                        "channels": ["bus_stop_designation_source", "bus_stop_geometry_source", "pedestrian_position_source"],
                        "source_refs": ["native/branch_runner.py", "native/branch_meter.py"]},
        "st.bench": {"evidence": "original bench geometry and public mass transportation use, separately reviewed",
                     "channels": ["bench_geometry_source", "bench_public_mass_transport_use_source", "pedestrian_position_source"],
                     "source_refs": ["native/branch_runner.py", "native/branch_meter.py"]},
        "st.shelter": {"evidence": "original shelter geometry and public mass transportation use, separately reviewed",
                       "channels": ["shelter_geometry_source", "shelter_public_mass_transport_use_source", "pedestrian_position_source"],
                       "source_refs": ["native/branch_runner.py", "native/branch_meter.py"]},
        "st.transit_stop": {"evidence": "original transit-stop designation and pedestrian location; label alone is insufficient",
                            "channels": ["stop_designation_source", "stop_furniture_geometry_source", "pedestrian_position_source"],
                            "source_refs": ["native/branch_runner.py", "native/branch_meter.py"]},
        "ru.bus": {"evidence": "original bus class, door side and continuous pedestrian boarding movement",
                   "channels": ["transit_vehicle_class_source", "door_side_source", "boarding_motion_source"],
                   "source_refs": ["native/branch_runner.py", "native/branch_meter.py"]},
        "ru.other_public_transport": {"evidence": "original other public transportation vehicle class, door side and continuous boarding movement",
                                      "channels": ["other_public_transport_class_source", "door_side_source", "boarding_motion_source"],
                                      "source_refs": ["native/branch_runner.py", "native/branch_meter.py"]},
        "drv.actual_observation": {"evidence": "separate driver or controller observation source; camera visibility and requested speed do not establish it",
                                   "channels": ["driver_observed_pedestrian", "driver_observation_source"],
                                   "source_refs": ["native/saved_measure.py", "native/finalize.py"]},
    })
    plan["blockers"] = [
        "All 11 textual position alternatives have separate cases, but original source surveys and physical execution are unverified.",
        "Actual driver observation has no independently accepted source; visibility and requested speed remain separate facts.",
        "Positive/negative selected compatibility, recorded-only, physical, semantic, independent delivery and comparison proofs are incomplete."]
    plan["runtime_uncertainties"] = [
        "Native map and actor blueprints can realize each original-source statutory position",
        "Original camera frames can inspect each decisive pedestrian and context relation",
        "Original driver observation and proper caution remain independent judgment calls",
        "Local canonical acceptance requires original capture, pixel and lifecycle audits"]
    store(plan_path, plan)
    dispositions = plan["requirement_dispositions"]
    audit = {"format": "worker-statutory-source-audit-v1",
             "assignment_id": ASSIGNMENT,
             "input_assignment_sha256": sha(source_path.read_bytes()),
             "exact_law_text_sha256": sha(law_text.encode()),
             "source": "NRS 484B.280(1)(c)",
             "plan_exact_text_matches_frozen": True,
             "selected_branch_activation_to_prove": "Original driver observation of a pedestrian in one sourced position; proper caution has no numeric statutory cutoff.",
             "position_alternatives": [{"branch": row["branch"], "case_ids": row["case_ids"],
                                        "status": "selected_cpu_preparation"}
                                       for row in dispositions],
             "planned_case_ids": [case["case_id"] for case in plan["cases"]],
             "original_source_measurements_required": "Independent survey of each position; original pedestrian and ego identities and frame-joined poses; separate perception source; measured response; independent caution judgment.",
             "review_disposition": "open_cpu_delivery_proofs",
             "physical_outcome": "unmeasured", "accepted_recording_equivalence": "unproven"}
    store(ROOT / "statutory-source-audit.json", audit)
    print(json.dumps({"alternatives": len(dispositions), "cases": len(audit["planned_case_ids"]),
                      "audit_sha256": sha((ROOT / "statutory-source-audit.json").read_bytes())}))


if __name__ == "__main__":
    main()
