"""Build source-bound C110454 queue intent; never dispatch partial cases."""
from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
PY = ".venv-cpu/bin/python"
EXCHANGE = f"PYTHONPATH=runtime/pipeline/scenario_pipeline {PY} -m worker_exchange"
MANIFEST = f"work/{AID}/execution-manifest.json"
PAIRS = {"rail", "oneway", "traversal"}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*parts):
    return " ".join(part if part.startswith("${") and part.endswith("}") else shlex.quote(part)
                    for part in parts)


def build():
    manifest_path, plan_path = HERE / "execution-manifest.json", HERE / "case-plan.json"
    manifest, plan = json.loads(manifest_path.read_text()), json.loads(plan_path.read_text())
    require(manifest.get("assignment_id") == plan.get("assignment_id") == AID,
            "Assignment identity differs")
    cases = manifest["cases"]
    require(len(cases) == 6 and len({entry["case_id"] for entry in cases}) == 6,
            "Expected six distinct selected cases")
    planned = {case["case_id"] for case in plan["cases"]}
    require({entry["case_id"] for entry in cases} <= planned,
            "Selected case absent from plan")
    rows = []
    for order, entry in enumerate(cases, 1):
        case = entry["case_id"]
        require(entry.get("kind") == "delivery" and entry.get("id") == "primary",
                "Selected delivery primary missing")
        candidates = entry["candidates"]
        require({item["id"] for item in candidates} == {"fallback1", "fallback2", "fallback3"},
                "Three distinct fallback IDs required")
        require(len({item["construction_sha256"] for item in [entry, *candidates]}) == 4,
                "Candidate constructions must differ")
        for candidate in [entry, *candidates]:
            path = HERE / candidate["construction"]
            require(path.is_file() and sha(path) == candidate["construction_sha256"],
                    "Selected construction hash differs: " + case + ":" + candidate["id"])
        identity = ("--repo", ".", "--batch", "full-train-delivery", "--db", "${WORKER_DB}",
                    "--assignment", AID, "--case", case)
        def prepare(candidate):
            return command(*shlex.split(EXCHANGE), "prepare-delivery", *identity,
                           "--candidate", candidate)
        rows.append({
            "order": order, "assignment_id": AID, "case_id": case,
            "status": "partial", "dispatchable": False,
            "construction_sha256": entry["construction_sha256"],
            "capture_command": command(PY, "runtime.py", "capture", "--manifest", MANIFEST,
                                       "--case", case, "--candidate", "primary",
                                       "--output", "${ATTEMPT_DIR}", "--host", "${CARLA_HOST}",
                                       "--port", "${CARLA_PORT}", "--python", "${NATIVE_PYTHON}"),
            "postprocessing_command": command(PY, "runtime.py", "process-saved", "--manifest", MANIFEST,
                                              "--case", case, "--attempt", "${ATTEMPT_DIR}",
                                              "--output", "${PROCESSED_DIR}", "--library", "${DECODER_LIBRARY}",
                                              "--validator", "${VALIDATOR}",
                                              "--owner-release-receipt", "${OWNER_RELEASE_RECEIPT}"),
            "owner_release_command": command("CASE_ID=" + case, PY, "runtime.py", "owner-released", "--attempt", "${ATTEMPT_DIR}",
                                             "--receipt", "${OWNER_RELEASE_RECEIPT}",
                                             "--acknowledge-owner-released"),
            "additional_source_audit_command": command(PY, "state/operations/worker_exchange/full-train-delivery/delivery_audit.py",
                                                       "--case", case, "--candidate", "${CANDIDATE_ID}",
                                                       "--construction-sha256", "${CONSTRUCTION_SHA256}",
                                                       "--attempt", "${ATTEMPT_DIR}",
                                                       "--processing", "${PROCESSED_DIR}/processing.json",
                                                       "--pixel-review", "${PIXEL_REVIEW}",
                                                       "--context-review", "${CONTEXT_REVIEW}",
                                                       "--primary-video", "${PRIMARY_VIDEO}",
                                                       "--core-trace", "${CORE_TRACE}",
                                                       "--decode-receipt", "${SOURCE_DECODE_RECEIPT}",
                                                       "--job-id", "${JOB_ID}",
                                                       "--attempt-number", "${ATTEMPT_NUMBER}",
                                                       "--recording-id", "${RECORDING_ID}",
                                                       "--output", "${SOURCE_AUDIT}"),
            "prepare_command": prepare("primary"),
            "execute_command": command(*shlex.split(EXCHANGE), "execute-delivery", *identity,
                                       "--run", "${RUN_ID}", "--job", "${JOB_ID}",
                                       "--python", "${NATIVE_PYTHON}", "--host", "${CARLA_HOST}",
                                       "--port", "${CARLA_PORT}"),
            "accept_command": command(*shlex.split(EXCHANGE), "accept-delivery", *identity,
                                      "--run", "${RUN_ID}", "--job", "${JOB_ID}",
                                      "--attempt", "${ATTEMPT_ID}", "--audit", "${ACCEPTANCE_AUDIT}"),
            "candidate_commands": {item["id"]: prepare(item["id"]) for item in candidates},
        })
    comparisons = []
    selected = {row["case_id"] for row in rows}
    for item in plan["comparisons"]:
        kind = item["comparison_id"].removeprefix(AID + "__comparison_")
        if kind not in PAIRS:
            continue
        require(len(item["case_ids"]) == 2 and set(item["case_ids"]) <= selected,
                "Selected comparison references unselected case")
        comparisons.append({"assignment_id": AID, "comparison_id": item["comparison_id"],
                            "case_ids": item["case_ids"], "status": "partial", "dispatchable": False,
                            "command": command(PY, f"work/{AID}/comparison_audit.py", "--kind", kind,
                                               "--left-attempt", "${LEFT_ATTEMPT_DIR}",
                                               "--left-saved", "${LEFT_PROCESSED_DIR}",
                                               "--right-attempt", "${RIGHT_ATTEMPT_DIR}",
                                               "--right-saved", "${RIGHT_PROCESSED_DIR}",
                                               "--left-audit", "${LEFT_SOURCE_AUDIT}",
                                               "--right-audit", "${RIGHT_SOURCE_AUDIT}",
                                               "--output", "${COMPARISON_AUDIT}")})
    require(len(comparisons) == 3, "Selected comparisons incomplete")
    return {"format": "c110454-selected-queue-fragment-v1", "assignment_id": AID,
            "manifest_sha256": sha(manifest_path), "case_plan_sha256": sha(plan_path),
            "status": "partial", "dispatchable": False, "cases": rows,
            "comparison_audit_commands": comparisons,
            "withheld_comparison_id": AID + "__comparison_main",
            "missing_to_dispatch": ["original Native delivery audits and pixel/context reviews",
                                    "original Native comparison receipts",
                                    "accepted-original 100-foot equivalence disposition",
                                    "complete selected manifest proof fields",
                                    "canonical batch queue and local integration proof"]}


if __name__ == "__main__":
    fragment = build()
    path = HERE / "update020-selected-queue-fragment.json"
    path.write_text(json.dumps(fragment, indent=2) + "\n")
    print(json.dumps({"cases": len(fragment["cases"]),
                      "fallback_commands": sum(len(row["candidate_commands"]) for row in fragment["cases"]),
                      "comparisons": len(fragment["comparison_audit_commands"]),
                      "dispatchable": fragment["dispatchable"]}))
