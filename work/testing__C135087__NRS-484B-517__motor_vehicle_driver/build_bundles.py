"""Build eight exact, source-gated taxicab stand diagnostic bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCES = ("runner.py", "stand.py", "stand_capture.py", "stand_delivery.py",
           "stand_media_audit.py", "analysis.py", "tests/test_bundle.py")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def recording_description():
    names = (
        ("official stand designation and sign", "SHA-sealed site record and Native sign readback"),
        ("subject passenger vehicle and driver", "SHA-sealed class record and Native actor ID"),
        ("taxicab entrant and approach", "SHA-sealed class record and Native actor/path readback"),
        ("loading, waiting, entry and access", "900 original 20 Hz observer and actor rows"),
        ("four synchronized camera views", "four original 20 Hz Native RGB streams"),
    )
    return {"channels": [{"name": name, "unit": "source observation", "sampling_rate_hz": 20,
                           "method": method, "time_window": "original 45-second episode",
                           "reference_frame": "original Native frame and time",
                           "uncertainty": "Original physical and legal review pending"}
                          for name, method in names],
            "context_inputs": [{"name": "reviewed stand, sign, map and vehicle classification sources",
                                "unit": "source record", "method": "SHA-256 sealed original packet"}],
            "limitations": ["Synthetic fixtures cannot establish sign adequacy, expedience or interference."]}


def build():
    plan_path = HERE / "case-plan.json"
    body = plan_path.read_bytes()
    plan = json.loads(body)
    cases = plan["cases"]
    if len(cases) != 8 or len({c["case_id"] for c in cases}) != 8:
        raise ValueError("eight exact stand cases required")
    files = {name: (HERE / name).read_text() for name in SOURCES}
    manifest_cases = []
    for case in cases:
        cid = case["case_id"]
        if not cid.startswith(AID + "__"):
            raise ValueError("foreign exact case")
        suffix = cid.removeprefix(AID + "__")
        config = {"assignment_id": AID, "law_id": "NRS-484B-517", "cell_id": "C135087",
                  "actor": "motor_vehicle_driver", "selected_case_id": cid,
                  "case_modes": {key: case[key] for key in ("loading_mode", "entrant_mode", "access_mode")},
                  "plan_sha256": sha(body), "fps": 20, "rate_hz": 20,
                  "frame_count": 900, "duration_s": 45,
                  "cameras": [{"name": name, "width": 1920 if name == "overview" else 1280,
                               "height": 1080 if name == "overview" else 720, "fov_deg": 90,
                               "pose_strategy": "reviewed stand-relative Native RGB sensor"}
                              for name in ("overview", "approach", "reference_corner", "driver_reference")],
                  "required_atoms": [],
                  "required_sources": ["reviewed_site_designation_sign", "vehicle_classification",
                                       "original_actor_rows", "original_four_camera_media"],
                  "physical_completion": {"criterion": "travel_progress", "motion_source": "trace.jsonl",
                                          "position_key": "position_m", "minimum_progress_m": 1.0,
                                          "completion_goal_method": "Observed at least 1 m approach progress before the sourced stand stop; engineering diagnostic only, not a legal cutoff"},
                  "case": {"case_id": cid, "recording_description": recording_description()},
                  "diagnostic_only": True}
        contents = dict(files, **{"case-plan.json": body.decode(),
                                  "config.json": json.dumps(config, indent=2) + "\n"})
        construction = {"law_id": config["law_id"], "cell_id": config["cell_id"],
                        "actor": config["actor"], "case_id": cid, "entrypoint": "runner.py",
                        "diagnostic_only": True, "recording_description": recording_description(),
                        "files": [{"path": name, "content": content} for name, content in contents.items()]}
        target = HERE / f"construction-{suffix}.json"
        target.write_text(json.dumps(construction, indent=2) + "\n")
        fallback = json.loads(target.read_text())
        for item in fallback["files"]:
            if item["path"] == "config.json":
                alternate = json.loads(item["content"])
                alternate["stand_offset_m"] = 0.25
                alternate["engineering_candidate"] = "fallback1"
                item["content"] = json.dumps(alternate, indent=2) + "\n"
        fallback_target = HERE / f"construction-{suffix}-fallback1.json"
        fallback_target.write_text(json.dumps(fallback, indent=2) + "\n")
        manifest_cases.append({"case_id": cid, "construction": target.name,
                               "construction_sha256": sha(target.read_bytes()),
                               "candidate_risk": case["physical_risk"],
                               "candidates": [{"id": "fallback1", "construction": fallback_target.name,
                                               "construction_sha256": sha(fallback_target.read_bytes()),
                                               "trigger": {"source": "Native subject spawn and curb readback",
                                                           "metric": "subject stand placement accepted inside reviewed curb polygon",
                                                           "failure_condition": "primary stand waypoint rejects spawn or loses curb visibility"},
                                               "changed_knobs": ["source-bounded stand_offset_m=0.25"]}]})
    draft = {"assignment_id": AID, "status": "diagnostic_original_sources_pending",
             "cases": manifest_cases}
    (HERE / "execution-manifest.draft.json").write_text(json.dumps(draft, indent=2) + "\n")
    root = json.loads((HERE / manifest_cases[0]["construction"]).read_text())
    (HERE / "construction.json").write_text(json.dumps(root, indent=2) + "\n")
    for entry in root["files"]:
        if entry["path"] == "config.json":
            (HERE / "config.json").write_text(entry["content"])
    print("built", len(manifest_cases), "source-gated stand bundles")


if __name__ == "__main__":
    build()
