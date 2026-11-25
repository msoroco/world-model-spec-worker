"""Build two exact current-runtime delivery constructions and risk fallbacks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parents[1]
REPO = FOLDER.parents[1]
AID = FOLDER.name
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def selected(case, candidate):
    name = case + "-" + candidate
    base = json.loads((HERE / "runtime-drafts" / case / candidate / "construction.json").read_text())
    files = [dict(entry) for entry in base["files"]]
    config = json.loads(next(row["content"] for row in files if row["path"] == "config.json"))
    config.update(status="selected_delivery_request", selected_case_id=AID + "__" + case,
                  cell_id="C10365", law_id="LVMC-11-40-070", actor="cycle_or_scooter_operator",
                  case_plan_sha256=sha(FOLDER / "case-plan.json"), duration_s=30, rate_hz=20,
                  camera_sources={name: [width, height] for name, width, height in CAMERAS},
                  cameras=[{"name": name, "width": width, "height": height,
                            "pose_strategy": "source-bound rider, officer and device coverage",
                            "fov_deg": 90} for name, width, height in CAMERAS],
                  required_atoms=["kin.speed"], source_packets=[], mandatory_channels=["kin.speed"])
    description = {"channels": [{"name": "kin.speed", "unit": "m/s", "sampling_rate_hz": 20,
                  "method": "derive original rider velocity from joined Native actor frames",
                  "time_window": "entire 30 s / 600-frame attempt",
                  "reference_frame": "original Native frame/time join",
                  "uncertainty": "50 ms sample; no legal threshold"}],
                  "context_inputs": [],
                  "limitations": ["Police Officer authority, contrary direction, device applicability and legal outcome require independent original review"]}
    config["recording_description"] = description
    config["case"] = {"case_id": AID + "__" + case, "recording_description": description}
    replacements = {"case-plan.json": (FOLDER / "case-plan.json").read_text(),
                    "config.json": json.dumps(config, indent=2, allow_nan=False) + "\n",
                    "check.py": (HERE / "check_selected.py").read_text(),
                    "capture.py": (HERE / "capture.py").read_text(),
                    "saved.py": (HERE / "saved_current_v2.py").read_text()}
    for row in files:
        if row["path"] in replacements:
            row["content"] = replacements[row["path"]]
    files.append({"path": "finalize.py", "content": (HERE / "finalize_selected.py").read_text()})
    base["files"] = files
    base["recording_description"] = description
    base["status"] = "selected_delivery_cpu_candidate"
    path = HERE / "selected-constructions" / (name + ".json")
    path.parent.mkdir(exist_ok=True)
    write(path, base)
    contract = {"format": "worker-measurement-contract", "case_id": AID + "__" + case,
                "requirements": [{"disposition_index": 0,
                                  "requirement": "LVMC-11-40-070", "source": "LVMC 11.40.070",
                                  "output_key": "device_response", "method": "measure_device_response",
                                  "value_type": "object", "kind": "measured",
                                  "inputs": ["raw.jsonl", "video_frames.jsonl", "review.json"]}],
                "negative": {"remove": ["review.json"],
                             "error_contains": "Missing required source: review.json"}}
    contract_path = HERE / "selected-contracts" / (name + ".json")
    contract_path.parent.mkdir(exist_ok=True)
    write(contract_path, contract)
    return {"id": candidate, "construction": path.relative_to(FOLDER).as_posix(),
            "construction_sha256": sha(path),
            "measurement_contract": contract_path.relative_to(FOLDER).as_posix(),
            "measurement_procedure": {"entrypoint": "finalize.py", "output_schema": "c10365-selected-source-analysis-v1"},
            "fixture_recipe": (HERE / "selected-recipes" / (name + ".json")).relative_to(REPO).as_posix()}


def build():
    cases = []
    proposal = json.loads((FOLDER / "proposals/cases.json").read_text())
    for case in ("probe_a", "probe_b"):
        primary = selected(case, "primary")
        fallbacks = [selected(case, name) for name in ("fallback1", "fallback2")]
        construction = json.loads((FOLDER / primary["construction"]).read_text())
        planned = next(row for row in proposal["cases"] if row["case_id"] == AID + "__" + case)
        planned["recording_description"] = construction["recording_description"]
        planned["target_type"] = "compliant_attempt" if case == "probe_a" else "officer_exception_attempt"
        planned["unresolved_judgment_calls"] = []
        cases.append({"case_id": AID + "__" + case, "kind": "draft_selected_cpu_probe",
                      **{key: value for key, value in primary.items() if key != "id"},
                      "candidates": fallbacks})
    proposal["status"] = "draft"
    proposal["sweep_specs"] = []
    proposal["sweeps_expanded"] = True
    write(FOLDER / "proposals/cases.json", proposal)
    write(FOLDER / "selected-probe-manifest.json", {
        "format": "worker-unselected-current-v2-probe-manifest",
        "assignment_id": AID, "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "status": "selected_cpu_proof_in_progress", "cases": cases})
    return {"cases": len(cases), "candidate_constructions": 6}


if __name__ == "__main__":
    print(json.dumps(build()))
