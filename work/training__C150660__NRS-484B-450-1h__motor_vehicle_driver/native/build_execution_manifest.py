"""Bind all selected exact cases to their tested source-hashed CPU candidates."""

import hashlib
import json
from pathlib import Path

from case_specs import CASES

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(FOLDER))


def offline(suffix, candidate, construction_sha):
    log = FOLDER / "native" / (suffix + "-" + candidate + "-offline.log")
    if not log.is_file():
        raise ValueError("Missing exact offline log: " + suffix + " " + candidate)
    command = (".venv-cpu/bin/python -B runtime.py offline --manifest work/" + FOLDER.name +
               "/draft-construction-manifest.json --case " + FOLDER.name + "__" + suffix +
               " --output .runtime-work/c150660-offline-" + suffix + "-" + candidate +
               " --python .venv-cpu/bin/python")
    if candidate != "primary":
        command += " --candidate " + candidate
    return {"command": command, "construction_sha256": construction_sha,
            "exit_code": 0, "log": relative(log), "log_sha256": sha(log)}


def compatibility(suffix, candidate, construction_sha):
    directory = FOLDER / "compatibility" / suffix / candidate
    receipt = directory / "compatibility.json"
    analysis = directory / "analysis.log"
    negative = directory / "negative.log"
    data = json.loads(receipt.read_text())
    if (data.get("passed") is not True or data.get("case_id") != FOLDER.name + "__" + suffix or
            data.get("candidate_id") != candidate or
            data.get("construction_sha256") != construction_sha or
            data.get("log_sha256") != sha(analysis) or
            data.get("negative_log_sha256") != sha(negative)):
        raise ValueError("Stale selected compatibility: " + suffix + " " + candidate)
    return {"receipt": relative(receipt), "sha256": sha(receipt),
            "log": relative(analysis), "negative_log": relative(negative)}


def post_capture(suffix, case, construction_sha):
    receipt = FOLDER / "saved" / (suffix + "-processing.json")
    log = FOLDER / "saved" / (suffix + "-processing.log")
    proof = json.loads(receipt.read_text())
    if (proof.get("passed") is not True or proof.get("recorded_only") is not True or
            proof.get("missing_evidence") is not False or
            proof.get("analysis_revision", {}).get("construction_sha256") != construction_sha):
        raise ValueError("Stale exact saved-only processing: " + case)
    return {"command": ".venv-cpu/bin/python runtime.py process-saved --case " + case +
            " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER",
            "feedback_command": ".venv-cpu/bin/python runtime.py feedback-saved --case " + case +
            " --attempt $ATTEMPT --output $SAVED_OUTPUT",
            "recorded_only": True, "test_exit_code": 0,
            "test_log": relative(log), "test_log_sha256": sha(log),
            "processing_receipt": relative(receipt), "processing_receipt_sha256": sha(receipt)}


def build():
    delivery = json.loads((FOLDER / "delivery-proof/receipts.json").read_text())
    cases = []
    for suffix in CASES:
        case = FOLDER.name + "__" + suffix
        primary = FOLDER / "cases" / suffix / "primary/construction.json"
        fallback = FOLDER / "cases" / suffix / "fallback1/construction.json"
        main_sha, alternative_sha = sha(primary), sha(fallback)
        construction = json.loads(primary.read_text())
        physical = FOLDER / "physical-proof" / suffix / "proof.json"
        entry = {"id": suffix, "case_id": case, "kind": "delivery",
                 "construction": relative(primary), "construction_sha256": main_sha,
                 "recording_description": construction["recording_description"],
                 "measurement_contract": "cases/" + suffix + "/measurement-contract.json",
                 "measurement_procedure": {"entrypoint": "finalize.py"},
                 "fixture_recipe": "work/" + FOLDER.name + "/native/diagnostic/" + suffix + "/fixture-recipe.json",
                 "offline": offline(suffix, "primary", main_sha),
                 "compatibility": compatibility(suffix, "primary", main_sha),
                 "post_capture": post_capture(suffix, case, main_sha),
                 "delivery_acceptance": delivery[suffix],
                 "negative": {"log": "compatibility/" + suffix + "/primary/negative.log"},
                 "candidate_risk": {"status": "physical",
                                    "reason": "Open-loop primary brake timing can miss the requested safety-zone footprint position on Native dynamics."},
                 "candidates": [{"id": "fallback1", "construction": relative(fallback),
                                 "construction_sha256": alternative_sha,
                                 "changed_knobs": ["brake_lead_seconds: 1.4 to 2.0; exact case, cameras and observations fixed"],
                                 "trigger": {"source": "original zone_raw.json and trace.jsonl",
                                             "metric": "observed final footprint distance or between-zone occupancy",
                                             "failure_condition": "Primary final rest misses its engineering target by more than 0.25 m"},
                                 "offline": offline(suffix, "fallback1", alternative_sha),
                                 "compatibility": compatibility(suffix, "fallback1", alternative_sha)}],
                 "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                    "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                 "physical_preparation": {"receipt": relative(physical), "sha256": sha(physical)},
                 "acquisition": {channel["name"]: {"entrypoint": "runner.py",
                                                   "evidence": "zone_raw.json, trace.jsonl, video_frames.jsonl, capture/evidence.jsonl, road.xodr, context-survey.json",
                                                   "method": "Original Native frame, map and independent source review"}
                                 for channel in construction["recording_description"]["channels"]}}
        cases.append(entry)
    manifest = {"format": "worker-execution-manifest", "status": "draft",
                "assignment_id": FOLDER.name,
                "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
                "cases": cases}
    path = FOLDER / "execution-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


if __name__ == "__main__":
    print(build())
