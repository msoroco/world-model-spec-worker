"""Bind the eight tested 600-frame paths for selection review.

This is an incremental CPU selection artifact. It does not assert delivery readiness.
"""
import copy
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def proof(case, candidate, construction_sha):
    suffix = "a" if case == "condition_a" else "b"
    source = ROOT / ".runtime-work" / f"c110763-current-matrix-{suffix}-{candidate}"
    names = {
        "receipt": "compatibility.json",
        "analysis_log": "compatibility-analysis.log",
        "negative_log": "negative-analysis.log",
    }
    copied = {}
    for key, name in names.items():
        target = FOLDER / f"selected-{case}-{candidate}-{name}"
        shutil.copyfile(source / name, target)
        copied[key] = target
    receipt = json.loads(copied["receipt"].read_text())
    assert receipt["passed"] is True
    assert receipt["candidate_id"] == candidate
    assert receipt["construction_sha256"] == construction_sha
    assert receipt["log_sha256"] == digest(copied["analysis_log"])
    assert receipt["negative_log_sha256"] == digest(copied["negative_log"])
    offline = FOLDER / f"selected-offline-{case}-{candidate}.log"
    if not offline.is_file():
        offline = FOLDER / f"current-600-offline-{case}-{candidate}.log"
    saved_name = f"current-600-saved-{suffix}-primary.log" if candidate == "primary" else f"current-600-saved-{case}-{candidate}.log"
    saved = FOLDER / saved_name
    assert offline.is_file() and saved.is_file()
    assert "Traceback" not in offline.read_text()
    assert "Traceback" not in saved.read_text()
    return {
        "offline": {
            "exit_code": 0,
            "construction_sha256": construction_sha,
            "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{FOLDER.name}/execution-manifest.json --case {receipt['case_id']} --candidate {candidate} --output .runtime-work/c110763-selected-offline-v2-{case}-{candidate}",
            "log": offline.name,
            "log_sha256": digest(offline),
        },
        "compatibility": {
            "receipt": copied["receipt"].name,
            "sha256": digest(copied["receipt"]),
            "log": copied["analysis_log"].name,
            "negative_log": copied["negative_log"].name,
        },
        "saved_cpu_proof": {
            "exit_code": 0,
            "log": saved.name,
            "log_sha256": digest(saved),
            "scope": "diagnostic saved processing, not original Native capture",
        },
    }


def main():
    draft = json.loads((FOLDER / "current-compat-matrix-manifest.json").read_text())
    draft = copy.deepcopy(draft)
    draft["format"] = "worker-execution-manifest"
    draft["status"] = "selected_cpu_partial"
    for entry, case in zip(draft["cases"], ("condition_a", "condition_b")):
        entry["kind"] = "delivery"
        entry.update(proof(case, "primary", entry["construction_sha256"]))
        entry["native_handoff"] = {
            "python_env_var": "CARLA_PYTHON",
            "host_env_var": "CARLA_HOST",
            "port_env_var": "CARLA_PORT",
        }
        entry["negative"] = {"log": f"selected-{case}-primary-negative-analysis.log"}
        construction = json.loads((FOLDER / entry["construction"]).read_text())
        config = json.loads(next(file["content"] for file in construction["files"] if file["path"] == "config.json"))
        required = set(config.get("required_atoms", [])) | {item["name"] for item in construction["recording_description"]["channels"]}
        entry["acquisition"] = {
            name: {
                "entrypoint": "finalize.py",
                "method": "derive from retained frame-joined original Native samples, surveyed road geometry, and four synchronized source camera files",
                "evidence": "native_samples.jsonl; video_frames.jsonl; road_geometry.json; overview, approach, reference_corner, driver_reference source videos",
            }
            for name in sorted(required)
        }
        entry["selection_status"] = "candidate_selected_cpu_partial"
        physical = FOLDER / "selected-physical" / case / "proof.json"
        if physical.is_file():
            entry["physical_preparation"] = {
                "receipt": str(physical.relative_to(FOLDER)), "sha256": digest(physical)
            }
        for candidate in entry["candidates"]:
            candidate.update(proof(case, candidate["id"], candidate["construction_sha256"]))
    write(FOLDER / "execution-manifest.json", draft)
    print(json.dumps({"cases": len(draft["cases"]), "candidates": sum(1 + len(e["candidates"]) for e in draft["cases"]), "manifest_sha256": digest(FOLDER / "execution-manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
