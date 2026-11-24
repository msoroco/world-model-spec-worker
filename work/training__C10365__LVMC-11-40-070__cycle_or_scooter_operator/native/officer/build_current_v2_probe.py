"""Bind one unselected C10365 primary diagnostic to the current runtime CLI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE

ROOT = HERE.parents[3]
PACKAGE = HERE.parent.parent
CASE_ID = PACKAGE.name + "__probe_a"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def build():
    old = json.loads((HERE / "runtime-drafts/probe_a/primary/construction.json").read_text())
    config = json.loads(next(row["content"] for row in old["files"]
                             if row["path"] == "config.json"))
    channels = [{"name": "kin.speed", "unit": "m/s", "sampling_rate_hz": 20,
                 "method": "derive rider velocity from retained raw Native source",
                 "time_window": "entire 30 s / 600-frame attempt",
                 "reference_frame": "original Native frame/time join",
                 "uncertainty": "50 ms sample; no legal threshold"}]
    description = {"channels": channels, "context_inputs": [],
                   "limitations": ["Synthetic diagnostic; original Police Officer authority, "
                                   "visible direction and official device applicability unverified"]}
    config.update(selected_case_id=CASE_ID, cell_id="C10365",
                  law_id="LVMC-11-40-070", actor="cycle_or_scooter_operator",
                  duration_s=30, rate_hz=20,
                  required_atoms=["kin.speed"], source_packets=[],
                  mandatory_channels=["kin.speed"],
                  cameras=[{"name": name, "width": width, "height": height}
                           for name, width, height in (
                               ("overview", 1920, 1080), ("approach", 1280, 720),
                               ("reference_corner", 1280, 720),
                               ("driver_reference", 1280, 720))],
                  case={"case_id": CASE_ID,
                        "recording_description": description},
                  recording_description=description)
    construction = dict(old)
    construction["files"] = [dict(row) for row in old["files"]]
    for row in construction["files"]:
        if row["path"] == "config.json":
            row["content"] = json.dumps(config, indent=2, allow_nan=False) + "\n"
    construction["files"].append({"path": "finalize.py",
                                  "content": (HERE / "finalize_current_v2.py").read_text()})
    construction["recording_description"] = description
    construction["status"] = "unselected_current_v2_probe"
    construction_path = HERE / "current-v2-primary-construction.json"
    write(construction_path, construction)
    contract = {"format": "worker-measurement-contract", "case_id": CASE_ID,
                "requirements": [{"disposition_index": 0,
                                  "requirement": "LVMC-11-40-070",
                                  "source": "LVMC 11.40.070",
                                  "output_key": "device_response",
                                  "method": "measure_device_response",
                                  "value_type": "object", "kind": "measured",
                                  "inputs": ["raw.jsonl", "video.jsonl", "review.json"]}],
                "negative": {"remove": ["review.json"],
                             "error_contains": "Missing required source: review.json"},
                "status": "unselected_contract_draft"}
    contract_path = HERE / "current-v2-primary-measurement-contract.json"
    write(contract_path, contract)
    proposal_case = {"case_id": CASE_ID, "target_law_id": "LVMC-11-40-070",
                     "target_type": "controlled_probe",
                     "rationale": "Unselected ordinary-device diagnostic; no officer or legal verdict",
                     "variable_assignments": {
                         "officer_cue_requested": {"kind": "controller",
                                                   "value": "no_contrary_direction",
                                                   "unit": "categorical"},
                         "observed_officer_direction": {"kind": "subject_behavior",
                                                         "value": None,
                                                         "unit": "categorical"}},
                     "recording_description": description}
    write(PACKAGE / "proposals/cases.json", {
        "cell_id": "C10365", "actor": "cycle_or_scooter_operator",
        "status": "unselected_current_v2_probe", "cases": [proposal_case]})
    manifest_path = PACKAGE / "current-v2-probe-manifest.json"
    runtime_manifest = json.loads((ROOT / "batch.json").read_text())["runtime"]
    runtime_sha = runtime_manifest.get("manifest_sha256") or runtime_manifest.get("sha256")
    if not runtime_sha:
        runtime_sha = json.loads((ROOT / "work/training__C329610__NRS-484B-413-2__motor_vehicle_driver/current-v2-probe-manifest.json").read_text())["runtime_manifest_sha256"]
    write(manifest_path, {
        "format": "worker-unselected-current-v2-probe-manifest",
        "assignment_id": PACKAGE.name,
        "runtime_manifest_sha256": runtime_sha,
        "status": "draft_not_selected",
        "cases": [{"case_id": CASE_ID, "kind": "draft_not_selected",
                   "candidate_risk": {"status": "none",
                                      "reason": "This is an unselected primary software probe"},
                   "candidates": [],
                   "construction": construction_path.relative_to(PACKAGE).as_posix(),
                   "construction_sha256": sha(construction_path),
                   "measurement_contract": contract_path.relative_to(PACKAGE).as_posix(),
                   "measurement_procedure": {"entrypoint": "finalize.py",
                                             "status": "saved_source_diagnostic"},
                   "fixture_recipe": (HERE / "current-v2-primary-fixture-recipe.json")
                                     .relative_to(ROOT).as_posix()}]})
    return {"construction_sha256": sha(construction_path),
            "contract_sha256": sha(contract_path),
            "manifest_sha256": sha(manifest_path)}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
