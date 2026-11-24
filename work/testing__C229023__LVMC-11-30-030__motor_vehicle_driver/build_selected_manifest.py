"""Bind six exact crosswalk constructions and contracts to selected delivery.

The manifest remains partial until independent delivery acceptance and the
remaining canonical handoff proofs are supplied.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_construction import CASES
from crosswalk_measurements import ASSIGNMENT_ID

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compatibility(suffix: str, case_id: str, candidate_id: str,
                   construction_sha256: str) -> dict:
    prefix = "primary" if candidate_id == "primary" else "fallback1"
    base = Path("cases") / suffix
    receipt = base / (prefix + "-compatibility.json")
    analysis_log = base / (prefix + "-compatibility-analysis.log")
    negative_log = base / (prefix + "-compatibility-negative.log")
    proof = json.loads((HERE / receipt).read_text())
    if (proof.get("format") != "worker-package-compatibility" or
            proof.get("passed") is not True or proof.get("case_id") != case_id or
            proof.get("candidate_id") != candidate_id or
            proof.get("construction_sha256") != construction_sha256 or
            proof.get("runtime_manifest_sha256") != _sha(REPO / "runtime" / "SOURCE-MANIFEST.json") or
            _sha(HERE / analysis_log) != proof.get("log_sha256") or
            _sha(HERE / negative_log) != proof.get("negative_log_sha256")):
        raise ValueError("stale selected compatibility receipt: " + case_id + "/" + candidate_id)
    result = json.loads((HERE / "result.json").read_text())
    compact_name = "cpu-compatibility-" + ("fallback-" if candidate_id != "primary" else "") + suffix.replace("_", "-") + ".log"
    test = next((item for item in result["tests"] if item.get("log") == compact_name), None)
    if test is None or test.get("exit_code") != 0 or _sha(HERE / compact_name) != test.get("sha256"):
        raise ValueError("selected compatibility command missing: " + case_id + "/" + candidate_id)
    return {"command": test["command"], "exit_code": 0,
            "receipt": str(receipt), "sha256": _sha(HERE / receipt),
            "log": str(analysis_log), "negative_log": str(negative_log)}


def build(seal_offline: bool = False) -> dict:
    draft = json.loads((HERE / "execution-manifest.draft.json").read_text())
    expected = {ASSIGNMENT_ID + "__" + suffix for suffix in CASES}
    if draft.get("assignment_id") != ASSIGNMENT_ID or {row["case_id"] for row in draft["cases"]} != expected:
        raise ValueError("all six exact diagnostic constructions required")
    plan = json.loads((HERE / "case-plan.json").read_text())
    if {row["case_id"] for row in plan["cases"]} != expected:
        raise ValueError("selected case plan differs")
    fallback = json.loads((HERE / "fallback-draft.json").read_text()) if (HERE / "fallback-draft.json").is_file() else {"candidates": {}}
    rows = []
    for row in draft["cases"]:
        case_id = row["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT_ID + "__")
        construction = HERE / row["construction"]
        contract = HERE / "cases" / suffix / "measurement-contract.json"
        if not contract.is_file() or _sha(construction) != row["construction_sha256"]:
            raise ValueError("selected construction or measurement contract missing/changed")
        source = json.loads(construction.read_text())
        files = {item["path"] for item in source["files"]}
        if "analysis.py" not in files or "canonical_evidence.py" not in files or source["case_id"] != case_id:
            raise ValueError("selected saved analysis/source projection missing")
        offline = {"status": "pending selected-manifest proof"}
        if seal_offline:
            log_name = "cpu-selected-offline-" + suffix + ".log"
            log = HERE / log_name
            if not log.is_file():
                raise ValueError("selected offline proof missing: " + suffix)
            proof = json.loads(log.read_text())
            if (proof.get("case_id") != case_id or proof.get("candidate_id") != "primary" or
                    proof.get("offline_passed") is not True or proof.get("simulation_started") is not False):
                raise ValueError("exact selected offline proof failed: " + suffix)
            offline = {"command": ".venv-cpu/bin/python runtime.py offline --manifest "
                       + "work/" + ASSIGNMENT_ID + "/execution-manifest.json --case "
                       + case_id + " --output .runtime-work/lead-nov24-sixth/selected-" + suffix
                       + " --python $PWD/.venv-cpu/bin/python",
                       "exit_code": 0, "construction_sha256": row["construction_sha256"],
                       "log": log_name, "log_sha256": _sha(log)}
        candidates = [dict(fallback["candidates"][case_id])] if case_id in fallback["candidates"] else []
        for candidate in candidates:
            if _sha(HERE / candidate["construction"]) != candidate["construction_sha256"]:
                raise ValueError("fallback construction changed")
            candidate["compatibility"] = _compatibility(
                suffix, case_id, candidate["id"], candidate["construction_sha256"])
        selected = {
            "case_id": case_id, "kind": "delivery",
            "construction": row["construction"],
            "construction_sha256": row["construction_sha256"],
            "measurement_contract": str(contract.relative_to(HERE)),
            "measurement_contract_sha256": _sha(contract),
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "candidate_risk": row["candidate_risk"],
            "candidates": candidates,
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
            "offline": offline,
            "compatibility": _compatibility(suffix, case_id, "primary", row["construction_sha256"]),
            "negative": {"log": str(Path("cases") / suffix / "primary-compatibility-negative.log")},
            "acquisition": {
                "ego_body_history": {"entrypoint": "native_crosswalk_capture.py",
                                     "method": "NativeCrosswalkRecorder.append",
                                     "evidence": "sealed 20 Hz ego center, vertices, speed, actor source and frame identity"},
                "lead_body_history": {"entrypoint": "native_crosswalk_capture.py",
                                      "method": "NativeCrosswalkRecorder.append",
                                      "evidence": "sealed 20 Hz lead center, vertices, speed, actor source and frame identity"},
                "original_actor_body_sequence": {"entrypoint": "native_crosswalk_capture.py",
                                                 "method": "NativeCrosswalkRecorder.append",
                                                 "evidence": "same-tick ego, lead and pedestrian actor identities"},
                "pedestrian_history": {"entrypoint": "native_crosswalk_capture.py",
                                       "method": "NativeCrosswalkRecorder.append",
                                       "evidence": "same-tick pedestrian center and actor source"},
                "four_camera_frame_map": {"entrypoint": "native_crosswalk_media.py",
                                          "method": "NativeCrosswalkCameras.append",
                                          "evidence": "four FFV1 frame records joined to world frame"},
                "complete_native_source_and_pixels": {"entrypoint": "native_crosswalk_media.py",
                                                      "method": "NativeCrosswalkCameras.close",
                                                      "evidence": "four completed FFV1 files and sealed camera frame map"},
            },
            "missing_proofs": [
                "independent selected delivery acceptance and canonical local dispatch",
                "reviewed original road intersection, stopped-purpose and Native camera source packets after CPU preparation",
            ],
        }
        physical_receipt = Path("cases") / suffix / "physical-preparation.json"
        physical_proof = json.loads((HERE / physical_receipt).read_text())
        if (physical_proof.get("case_id") != case_id or
                physical_proof.get("construction_sha256") != row["construction_sha256"] or
                {item.get("kind") for item in physical_proof.get("fixtures", [])} !=
                {"complete_motion", "incomplete_motion", "missing_evidence"}):
            raise ValueError("selected physical preparation proof differs: " + suffix)
        selected["physical_preparation"] = {"receipt": str(physical_receipt),
                                            "sha256": _sha(HERE / physical_receipt)}
        attempt = ("unmarked-pass-v4" if suffix == "unmarked_pass" else "compat-" + suffix)
        command = ("PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + ASSIGNMENT_ID +
                   "/delivery_audit.py --case " + case_id +
                   " --attempt .runtime-work/lead-nov24-converter/" + attempt + " --diagnostic-test")
        positive_log = Path("cases") / suffix / "delivery-positive.log"
        negative_log = Path("cases") / suffix / "delivery-negative.log"
        positive = json.loads((HERE / positive_log).read_text())
        if (positive.get("case_id") != case_id or positive.get("status") != "cpu_source_audit_passed" or
                positive.get("diagnostic_audit_test_passed") is not True or
                len(positive.get("videos_fully_decoded", {})) != 4 or
                any(count != 900 for count in positive["videos_fully_decoded"].values()) or
                "missing original context source" not in (HERE / negative_log).read_text()):
            raise ValueError("selected delivery auditor CPU proof differs: " + suffix)
        selected["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": _sha(HERE / "delivery_audit.py"),
            "command": command, "test_exit_code": 0,
            "test_log": str(positive_log), "test_log_sha256": _sha(HERE / positive_log),
            "negative_command": command + " --negative", "negative_exit_code": 1,
            "negative_expected_error": "missing original context source",
            "negative_log": str(negative_log), "negative_log_sha256": _sha(HERE / negative_log),
            "scope": "diagnostic CPU source and four-video audit; physical/legal acceptance unverified",
        }
        recipe = HERE / ("fixture-recipe-" + suffix + ".json")
        if not recipe.is_file():
            raise ValueError("exact diagnostic fixture recipe missing: " + suffix)
        selected["fixture_recipe"] = str(recipe.relative_to(REPO))
        selected["fixture_recipe_sha256"] = _sha(recipe)
        rows.append(selected)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT_ID,
                "runtime_manifest_sha256": _sha(REPO / "runtime" / "SOURCE-MANIFEST.json"),
                "status": "partial_selected_delivery", "cases": rows}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal-offline", action="store_true")
    args = parser.parse_args()
    print("bound", len(build(args.seal_offline)["cases"]),
          "exact selected crosswalk entries; proofs remain partial")
