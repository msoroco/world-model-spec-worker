"""Build immutable exact-case inline bundles from the reviewed driveway plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PLAN = json.loads((HERE / "case-plan.json").read_text())
AID = PLAN["assignment_id"]
CASES = PLAN["cases"]


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


recording_description = {
    "channels": [
        {"name": row["name"], "unit": "structured", "sampling_rate_hz": 20,
         "method": row["source"], "time_window": "full original 45 second episode",
         "reference_frame": "original Native frame and map coordinates",
         "uncertainty": "physical realization and camera coverage require local review"}
        for row in PLAN["observations"]
    ],
    "context_inputs": [
        {"name": "reviewed_residential_driveway_context", "unit": "source_packet",
         "method": "reviewed original map, frontage, ownership and driver identity"}
    ],
    "limitations": [
        "Fixture packets verify software conversion only; original CARLA geometry and camera coverage need local verification.",
        "No statutory cutoff is assigned to immediately prior, collision-avoidance necessity or right-of-way.",
    ],
}

proposal = {
    "status": "draft", "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
    "sweep_specs": [], "cases": [
        {"case_id": row["case_id"], "target_law_id": PLAN["law_id"],
         "target_type": "deterministic_probe", "rationale": row["deliberate_condition"],
         "variable_assignments": {"world_setup": row["world_setup"],
                                  "controller": row["controller"],
                                  "subject_behavior": row["subject_behavior"]},
         "unresolved_judgment_calls": ["immediately prior", "as may be necessary to avoid collision",
                                       "right-of-way to all vehicles approaching"],
         "recording_description": recording_description}
        for row in CASES
    ],
}
dump(HERE / "proposals/cases.json", proposal)

profile = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
cameras = [{"name": name, "width": width, "height": height,
            "pose_strategy": "reviewed original map survey with all critical bodies and boundaries",
            "fov_deg": 90} for name, width, height in profile]
plan_sha = hashlib.sha256((HERE / "case-plan.json").read_bytes()).hexdigest()
files = ("runner.py", "analysis.py", "driveway_construction.py", "driveway_controller.py",
         "driveway_measurement.py", "native_acquisition.py", "carla_driveway_adapter.py",
         "finalize_native.py", "delivery_audit.py", "comparison_audit.py",
         "case-plan.json", "tests/test_driveway.py")
for row in CASES:
    name = row["case_id"].split("__")[-1]
    config = {
        "assignment_id": AID, "selected_case_id": row["case_id"],
        "supported_case_ids": [c["case_id"] for c in CASES],
        "law_id": PLAN["law_id"], "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
        "case": row, "plan_sha256": plan_sha,
        "rate_hz": 20, "frame_count": 900, "duration_s": 45,
        "cameras": cameras, "required_atoms": [], "source_packets": [],
        "fallback_spawn_offset_m": 0,
    }
    construction = {
        "case_id": row["case_id"], "law_id": PLAN["law_id"],
        "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
        "entrypoint": "runner.py", "files": [
            {"path": path, "source": str((HERE / path).relative_to(REPO)),
             "content": (HERE / path).read_text()} for path in files
        ] + [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}],
        "measurement_plan": {
            "stop": "original ego speed and last halt position before first sidewalk body entry",
            "pedestrian": "original pedestrian and ego body motion and precedence with full source history",
            "roadway": "original left/right vehicle and ego body motion at road entry",
            "legal_cutoffs": None,
        },
        "recording_description": recording_description,
        "static_checks": ["source hash", "surveyed route order", "both roadway approaches",
                          "camera dimensions", "original 20 Hz frame join"],
        "termination_rules": ["record exactly 900 synchronized frames", "brake and restore on failure"],
        "mechanisms": ["reviewed private driveway through intervening sidewalk to connected roadway",
                       "ego route follower and stop/precedence controller",
                       "walker and both roadway approach controllers"],
    }
    dump(HERE / "cases" / name / "construction.json", construction)
    if row is CASES[0]:
        dump(HERE / "config.json", config)
        dump(HERE / "construction.json", construction)

manifest = {
    "format": "worker-execution-manifest", "assignment_id": AID,
    "runtime_manifest_sha256": hashlib.sha256((REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
    "cases": [
        {"case_id": row["case_id"], "kind": "delivery",
         "construction": "cases/" + row["case_id"].split("__")[-1] + "/construction.json",
         "construction_sha256": hashlib.sha256((HERE / "cases" / row["case_id"].split("__")[-1] / "construction.json").read_bytes()).hexdigest(),
         "candidate_risk": row["candidate_risk"], "candidates": [],
         "measurement_contract": "measurement-" + row["case_id"].split("__")[-1] + ".json",
         "fixture_recipe": "work/" + AID + "/diagnostic-" + row["case_id"].split("__")[-1] + "-recipe.json",
         "measurement_procedure": {"entrypoint": "analysis.py"},
         "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                            "port_env_var": "CARLA_PORT"}}
        for row in CASES
    ],
}
dump(HERE / "execution-manifest.json", manifest)
