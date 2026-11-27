"""Bind eight exact CPU proofs, fallbacks, audits and saved processing commands."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RUN = REPO / ".runtime-work" / "c230259-proof-run-v3"
PLAN = json.loads((ROOT / "case-plan.json").read_text())
ASSIGNMENT = PLAN["assignment_id"]
VALIDATOR = ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return path.relative_to(REPO).as_posix()


def proof(case, candidate):
    suffix = case["case_id"].split("__")[-1]
    label = suffix + ("" if candidate == "primary" else "-fallback1")
    offline = RUN / ("offline-" + suffix + "-" + candidate)
    compatible = RUN / ("compatibility-" + suffix + "-" + candidate)
    receipt_path = ROOT / ("compat-" + label + "-receipt.json")
    analysis_log = ROOT / ("compat-" + label + "-analysis.log")
    negative_log = ROOT / ("compat-" + label + "-negative.log")
    offline_log = ROOT / ("cpu-offline-" + label + ".log")
    for source, target in ((compatible / "compatibility.json", receipt_path),
                           (compatible / "compatibility-analysis.log", analysis_log),
                           (compatible / "negative-analysis.log", negative_log),
                           (offline / "offline.log", offline_log)):
        shutil.copyfile(source, target)
    receipt = json.loads(receipt_path.read_text())
    construction = ROOT / "cases" / suffix / ("construction.json" if candidate == "primary"
                                               else "construction-fallback1.json")
    if receipt["case_id"] != case["case_id"] or receipt["candidate_id"] != candidate:
        raise ValueError("compatibility proof case/candidate differs")
    if receipt["construction_sha256"] != sha(construction) or receipt["log_sha256"] != sha(analysis_log):
        raise ValueError("compatibility proof construction or analysis log changed")
    if receipt["negative_log_sha256"] != sha(negative_log):
        raise ValueError("negative source rejection log changed")
    command = (".venv-cpu/bin/python runtime.py offline --manifest " +
               rel(ROOT / "execution-manifest.draft.json") + " --case " + case["case_id"] +
               ("" if candidate == "primary" else " --candidate fallback1") +
               " --output .runtime-work/c230259-proof-run-v3/offline-" + suffix + "-" + candidate +
               " --python \"$PWD/.venv-cpu/bin/python\"")
    return ({"command": command, "construction_sha256": sha(construction),
             "exit_code": 0, "log": offline_log.name, "log_sha256": sha(offline_log)},
            {"receipt": receipt_path.name, "sha256": sha(receipt_path),
             "log": analysis_log.name,
             "negative_log": negative_log.name})


def main():
    manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    by_case = {entry["case_id"]: entry for entry in manifest["cases"]}
    script = ROOT / "delivery_audit.py"
    for case in PLAN["cases"]:
        suffix = case["case_id"].split("__")[-1]
        entry = by_case[case["case_id"]]
        offline, compatibility = proof(case, "primary")
        entry["offline"] = offline
        entry["compatibility"] = {key: compatibility[key] for key in ("receipt", "sha256", "log")}
        entry["negative"] = {"log": compatibility["negative_log"]}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        physical = ROOT / ("physical-preparation-" + suffix + ".json")
        entry["physical_preparation"] = {"receipt": physical.name, "sha256": sha(physical)}
        for candidate in entry["candidates"]:
            offline, compatible = proof(case, candidate["id"])
            candidate["offline"] = offline
            candidate["compatibility"] = compatible
        attempt = ".runtime-work/c230259-proof-run-v3/compatibility-" + suffix + "-primary"
        delivery_log = ROOT / ("delivery-diagnostic-" + suffix + ".log")
        negative_log = ROOT / ("delivery-negative-" + suffix + ".log")
        entry["delivery_acceptance"] = {"case_id": case["case_id"],
            "sets": ["full-test"], "checks": ["native_source", "all_participants",
                "time_join", "full_video_decode", "actual_pixels", "physical_completion"],
            "script": script.name, "script_sha256": sha(script),
            "command": ".venv-cpu/bin/python " + rel(script) + " --case " + case["case_id"] +
                       " --attempt " + attempt + " --output " +
                       rel(ROOT / ("delivery-diagnostic-" + suffix + ".json")) + " --diagnostic-fixture",
            "negative_command": ".venv-cpu/bin/python " + rel(script) + " --case " + case["case_id"] +
                       " --attempt " + attempt + " --output .runtime-work/c230259-proof-run-v3/delivery-negative-" +
                       suffix + ".json --diagnostic-fixture --negative-remove-source roi-frames.jsonl",
            "test_exit_code": 0, "test_log": delivery_log.name,
            "test_log_sha256": sha(delivery_log),
            "negative_exit_code": 1, "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log),
            "negative_expected_error": "Missing required source: roi-frames.jsonl"}
        lifecycle = ROOT / ("cpu-physical-lifecycle-" + suffix + ".log")
        entry["post_capture"] = {"command": ".venv-cpu/bin/python runtime.py process-saved --manifest " +
            rel(ROOT / "execution-manifest.json") + " --case " + case["case_id"] +
            " --attempt ORIGINAL_ATTEMPT --output .runtime-work/c230259-saved-" + suffix +
            " --library runtime/library --validator " + VALIDATOR +
            " --owner-release-receipt ORIGINAL_OWNER_RELEASE_RECEIPT",
            "feedback_command": "cat .runtime-work/c230259-saved-" + suffix + "/v0001/processing.json",
            "recorded_only": True, "test_exit_code": 0,
            "test_log": lifecycle.name, "test_log_sha256": sha(lifecycle)}
    manifest["status"] = "delivery_prepared_cpu_proofs"
    (ROOT / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
