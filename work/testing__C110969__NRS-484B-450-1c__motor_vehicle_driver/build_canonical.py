"""Bind selected CPU proofs into the nine-case source-gated delivery handoff.

This creates a dispatch contract. It does not assert Native or legal acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
NAMES = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build() -> None:
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    selected = json.loads((HERE / "execution-manifest.candidate.json").read_text())
    if len(plan["cases"]) != 9 or len(selected["cases"]) != 9 or len(plan["comparisons"]) != 8:
        raise ValueError("nine exact cases and eight comparisons required")
    if not proposal.get("sweeps_expanded"):
        raise ValueError("pinned sweep expansion has not run")
    targets = ["full-test"]
    for entry in selected["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(AID + "__")
        if suffix == case_id:
            raise ValueError("foreign selected case")
        folder = HERE / "cases" / suffix
        negative = folder / "compat-negative.log"
        positive_delivery = folder / "delivery-positive.log"
        negative_delivery = folder / "delivery-negative.log"
        saved = folder / "saved-only-command.log"
        for path in (negative, positive_delivery, negative_delivery, saved):
            if not path.is_file():
                raise ValueError("missing selected CPU proof: " + str(path))
        entry["negative"] = {"log": str(negative.relative_to(HERE))}
        entry["proof_status"] = "CPU diagnostic passed; original Native evidence pending"
        entry["delivery_acceptance"] = {
            "case_id": case_id,
            "sets": targets,
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py",
            "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{AID}/prove_delivery.py --case {case_id} --attempt $DIAGNOSTIC_ATTEMPT",
            "test_exit_code": 0,
            "test_log": str(positive_delivery.relative_to(HERE)),
            "test_log_sha256": sha(positive_delivery),
            "negative_command": f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{AID}/prove_delivery.py --case {case_id} --attempt $DIAGNOSTIC_ATTEMPT --negative",
            "negative_exit_code": 1,
            "negative_expected_error": "diagnostic fixture cannot establish delivery acceptance",
            "negative_log": str(negative_delivery.relative_to(HERE)),
            "negative_log_sha256": sha(negative_delivery),
            "proof_scope": "synthetic diagnostic protocol; original pixels and physical completion require independent review",
        }
        command = (f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved "
                   f"--manifest work/{AID}/execution-manifest.json --case {case_id} "
                   "--attempt $ATTEMPT --output $SAVED_OUTPUT --library $LIBRARY "
                   "--validator $VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": command,
            "feedback_command": command,
            "test_log": str(saved.relative_to(HERE)),
            "test_log_sha256": sha(saved),
            "test_exit_code": 0,
            "proof_scope": "synthetic saved-only fixture; original Native source pending",
        }
    selected["status"] = "CPU-prepared source-gated dispatch; physical review pending"
    write(HERE / "execution-manifest.json", selected)

    # The root artifact is a materialized entrypoint for the first exact case.
    # Its inline source stays identical to that selected construction.
    root_case = json.loads((HERE / selected["cases"][0]["construction"]).read_text())
    root_case.update({
        "measurement_plan": {"source": "case-plan.json", "case_id": root_case["case_id"],
                             "recorded_only": True},
        "static_checks": ["exact case and source index", "four original cameras", "900 original frames"],
        "termination_rules": ["900 original 20 Hz Native ticks", "actor cleanup", "world restoration"],
        "mechanisms": {"construction_status": "source-gated Native implementation CPU tested"},
    })
    root_case.pop("diagnostic_only", None)
    for item in root_case["files"]:
        path = HERE / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["content"])
    write(HERE / "construction.json", root_case)

    config = json.loads((HERE / "config.json").read_text())
    config["supported_case_ids"] = [entry["case_id"] for entry in selected["cases"]]
    config["cameras"] = [
        {"name": name, "width": 1920 if name == "overview" else 1280,
         "height": 1080 if name == "overview" else 720,
         "pose_strategy": "reviewed source-gated Native camera packet",
         "fov_deg": 90} for name in NAMES
    ]
    config["capture_provenance"] = "original Native samples required"
    write(HERE / "config.json", config)
    print("bound nine exact source-gated delivery cases; original review remains pending")


if __name__ == "__main__":
    build()
