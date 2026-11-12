"""Build C104538's exact selected delivery intent without dispatching it."""
import hashlib
import json
import shlex
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
PY = ".venv-cpu/bin/python"
RUNTIME = f"{PY} runtime.py"
EXCHANGE = f"PYTHONPATH=runtime/pipeline/scenario_pipeline {PY} -m worker_exchange"
MANIFEST = f"work/{AID}/execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*words):
    return " ".join(word if word.startswith("${") and word.endswith("}") else shlex.quote(word)
                    for word in words)


def build():
    manifest_path = HERE / "execution-manifest.json"
    plan_path = HERE / "case-plan.json"
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads(plan_path.read_text())
    assert manifest["assignment_id"] == plan["assignment_id"] == AID
    cases = manifest["cases"]
    assert len(cases) == 3
    assert {c["case_id"] for c in cases} == {c["case_id"] for c in plan["cases"]}
    assert len(plan["comparisons"]) == 1
    rows = []
    for order, entry in enumerate(cases, 1):
        case = entry["case_id"]
        candidates = entry["candidates"]
        assert {c["id"] for c in candidates} == {"fallback1", "fallback2", "fallback3"}
        for candidate in [entry, *candidates]:
            construction = HERE / candidate["construction"]
            assert construction.is_file() and sha(construction) == candidate["construction_sha256"]
        identity = ("--repo", ".", "--batch", "full-train-delivery", "--db", "${WORKER_DB}",
                    "--assignment", AID, "--case", case)
        prepare = lambda candidate: command(*shlex.split(EXCHANGE), "prepare-delivery", *identity,
                                            "--candidate", candidate)
        rows.append({
            "order": order, "assignment_id": AID, "case_id": case,
            "status": "partial", "dispatchable": False,
            "capture_command": command(PY, "runtime.py", "capture", "--manifest", MANIFEST,
                                       "--case", case, "--candidate", "primary", "--output", "${ATTEMPT_DIR}",
                                       "--host", "${CARLA_HOST}", "--port", "${CARLA_PORT}",
                                       "--python", "${NATIVE_PYTHON}"),
            "owner_release_command": command(f"CASE_ID={case}", PY, "runtime.py", "owner-released", "--attempt", "${ATTEMPT_DIR}",
                                              "--receipt", "${OWNER_RELEASE_RECEIPT}",
                                              "--acknowledge-owner-released"),
            "postprocessing_command": command(PY, "runtime.py", "process-saved", "--manifest", MANIFEST,
                                              "--case", case, "--attempt", "${ATTEMPT_DIR}",
                                              "--output", "${PROCESSED_DIR}", "--library", "${DECODER_LIBRARY}",
                                              "--validator", "${VALIDATOR}",
                                              "--owner-release-receipt", "${OWNER_RELEASE_RECEIPT}"),
            "additional_source_audit_command": command(PY, f"work/{AID}/delivery_audit.py", "--case", case,
                "--candidate", "${CANDIDATE_ID}", "--construction-sha256", "${CONSTRUCTION_SHA256}",
                "--attempt", "${ATTEMPT_DIR}", "--saved", "${PROCESSED_DIR}",
                "--owner-receipt", "${OWNER_RELEASE_RECEIPT}", "--pixel-review", "${PIXEL_REVIEW}",
                "--fixed-review", "${FIXED_REVIEW}", "--primary-video", "${PRIMARY_VIDEO}",
                "--core-trace", "${CORE_TRACE}", "--decode-dir", "${DECODE_DIR}",
                "--output", "${SOURCE_AUDIT}"),
            "prepare_command": prepare("primary"),
            "execute_command": command(*shlex.split(EXCHANGE), "execute-delivery", *identity,
                                       "--run", "${RUN_ID}", "--job", "${JOB_ID}",
                                       "--python", "${NATIVE_PYTHON}", "--host", "${CARLA_HOST}",
                                       "--port", "${CARLA_PORT}"),
            "accept_command": command(*shlex.split(EXCHANGE), "accept-delivery", *identity,
                                      "--run", "${RUN_ID}", "--job", "${JOB_ID}",
                                      "--attempt", "${ATTEMPT_ID}", "--audit", "${ACCEPTANCE_AUDIT}"),
            "candidate_commands": {candidate["id"]: prepare(candidate["id"]) for candidate in candidates},
        })
    comparison = plan["comparisons"][0]
    assert set(comparison["case_ids"]) == {entry["case_id"] for entry in cases}
    compare_command = command(f"COMPARISON_ID={comparison['comparison_id']}", PY,
                              f"work/{AID}/comparison_audit.py",
                              *(part for i in range(1, 4) for part in
                                ("--attempt", f"${{ATTEMPT_{i}_DIR}}", "--saved", f"${{PROCESSED_{i}_DIR}}")))
    return {"format": "c104538-selected-queue-fragment-v1", "assignment_id": AID,
            "manifest_sha256": sha(manifest_path), "case_plan_sha256": sha(plan_path),
            "status": "partial", "dispatchable": False, "cases": rows,
            "comparison_audit_commands": [{"assignment_id": AID, "comparison_id": comparison["comparison_id"],
                                           "case_ids": comparison["case_ids"], "status": "partial",
                                           "dispatchable": False, "command": compare_command}]}


if __name__ == "__main__":
    fragment = build()
    path = HERE / "update024-selected-queue-fragment.json"
    path.write_text(json.dumps(fragment, indent=2) + "\n")
    print(json.dumps({"cases": len(fragment["cases"]),
                      "fallback_commands": sum(len(c["candidate_commands"]) for c in fragment["cases"]),
                      "comparisons": len(fragment["comparison_audit_commands"]),
                      "dispatchable": fragment["dispatchable"]}))
