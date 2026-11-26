"""Bind current-runtime exact candidate, source and CPU proof receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = HERE.parents[2]
ASSIGNMENT = FOLDER.name
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def compatibility(letter, candidate):
    source = ROOT / ".runtime-work" / (f"c385967-{letter}-{candidate}-compat4"
        if letter in "ab" and len(letter) == 1 else f"c385967-{letter}-{candidate}-compat")
    names = {"compatibility.json": f"selected-{letter}-{candidate}-compatibility.json",
             "compatibility-analysis.log": f"selected-{letter}-{candidate}-compatibility-analysis.log",
             "negative-analysis.log": f"selected-{letter}-{candidate}-negative.log"}
    for original, destination in names.items():
        shutil.copyfile(source / original, HERE / destination)
    receipt = HERE / names["compatibility.json"]
    value = json.loads(receipt.read_text())
    if value.get("passed") is not True or value.get("candidate_id") != candidate:
        raise ValueError("Candidate compatibility did not pass")
    return {"receipt": "native/" + receipt.name, "sha256": sha(receipt),
            "log": "native/" + names["compatibility-analysis.log"],
            "negative_log": "native/" + names["negative-analysis.log"]}


def offline(letter, candidate, construction_sha):
    log = HERE / f"selected-{letter}-{candidate}-offline.log"
    if '"offline_passed": true' not in log.read_text():
        raise ValueError("Exact selected offline did not pass")
    action, condition = (letter.split("-", 1) if "-" in letter else ("park", letter))
    suffix = "" if action == "park" else action + "_"
    case = ASSIGNMENT + "__selected_03f318de__" + suffix + "condition_" + condition
    return {"command": ".venv-cpu/bin/python -B runtime.py offline --manifest work/" +
            ASSIGNMENT + "/native/selected-draft-manifest.json --case " + case +
            " --candidate " + candidate + " --output .runtime-work/c385967-" +
            letter + "-" + candidate + ("-offline4" if action == "park" else "-offline2"),
            "exit_code": 0, "construction_sha256": construction_sha,
            "log": "native/" + log.name, "log_sha256": sha(log)}


def main():
    entries = []
    for letter in ("a", "b", "stop-a", "stop-b", "stand-a", "stand-b"):
        action, condition = (letter.split("-", 1) if "-" in letter else ("park", letter))
        suffix = "" if action == "park" else action + "_"
        case = ASSIGNMENT + "__selected_03f318de__" + suffix + "condition_" + condition
        primary_path = HERE / f"selected-{letter}-construction.json"
        fallback_path = HERE / f"selected-{letter}-fallback1-construction.json"
        primary_sha, fallback_sha = sha(primary_path), sha(fallback_path)
        primary_compat = compatibility(letter, "primary")
        fallback_compat = compatibility(letter, "fallback1")
        accepted = HERE / f"selected-{letter}-saved-processing.json"
        rejected = HERE / f"selected-{letter}-saved-negative-feedback.json"
        saved_log = HERE / f"selected-{letter}-saved-test.log"
        if not (accepted.is_file() and rejected.is_file() and saved_log.is_file()):
            raise ValueError("Recorded-only positive/negative proof missing")
        positive, negative = (json.loads(path.read_text()) for path in (accepted, rejected))
        if positive.get("passed") is not True or \
                "Missing required source: official_device.json" not in negative.get("error", ""):
            raise ValueError("Recorded-only proof did not pass")
        acquisition = {}
        construction = json.loads(primary_path.read_text())
        names = {name["name"] for name in construction["recording_description"]["channels"]}
        names.update(("kin.heading", "kin.speed"))
        for name in names:
            acquisition[name] = {"entrypoint": "capture.py" if name in ("kin.heading", "kin.speed") else "finalize.py",
                "method": "source-joined original Native sample, device, curb, body and camera frame",
                "evidence": "native_samples.jsonl and channels/" + name + ".jsonl"}
        delivery_script = HERE / "delivery_audit.py"
        positive_log = HERE / f"delivery-{letter}-positive.log"
        negative_log = HERE / f"delivery-{letter}-negative.log"
        physical = HERE / f"physical-{letter}-receipt.json"
        entry = {"case_id": case, "kind": "delivery", "id": "primary",
            "construction": "native/" + primary_path.name,
            "construction_sha256": primary_sha,
            "candidate_risk": {"status": "physical",
                "reason": "Original at-rest body and speed can fail with hand brake alone"},
            "candidates": [{"id": "fallback1",
                "construction": "native/" + fallback_path.name,
                "construction_sha256": fallback_sha,
                "trigger": {"source": "original Native native_samples.jsonl",
                    "metric": "maximum at-rest ego_speed_mps",
                    "failure_condition": "original at-rest speed exceeds engineering 0.1 m/s diagnostic"},
                "changed_knobs": ["parking_brake_mode"],
                "offline": offline(letter, "fallback1", fallback_sha),
                "compatibility": fallback_compat}],
            "measurement_contract": f"native/selected-{letter}-measurement-contract.json",
            "measurement_procedure": {"entrypoint": "finalize.py", "status": "saved_source_diagnostic"},
            "fixture_recipe": "work/" + ASSIGNMENT + f"/native/selected-{letter}-fixture-recipe.json",
            "physical_preparation": {"receipt": "native/" + physical.name,
                "sha256": sha(physical), "scope": "synthetic CPU triad; original unverified"},
            "offline": offline(letter, "primary", primary_sha),
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
            "acquisition": acquisition,
            "negative": {"log": primary_compat["negative_log"]},
            "compatibility": primary_compat,
            "delivery_acceptance": {"case_id": case, "sets": ["full-train"],
                "checks": CHECKS, "script": "native/" + delivery_script.name,
                "script_sha256": sha(delivery_script),
                "command": ".venv-cpu/bin/python -B work/" + ASSIGNMENT +
                           "/native/delivery_audit.py --case " + case + " --selftest",
                "test_exit_code": 0, "test_log": "native/" + positive_log.name,
                "test_log_sha256": sha(positive_log),
                "negative_command": ".venv-cpu/bin/python -B work/" + ASSIGNMENT +
                                    "/native/delivery_audit.py --case " + case + " --negative-selftest",
                "negative_exit_code": 1,
                "negative_expected_error": "Reviewed pixel box exceeds source video",
                "negative_log": "native/" + negative_log.name,
                "negative_log_sha256": sha(negative_log),
                "scope": "synthetic CPU mechanics; original Native pixels remain"},
            "post_capture": {"recorded_only": True,
                "command": ".venv-cpu/bin/python -B runtime.py process-saved --manifest work/" +
                           ASSIGNMENT + "/execution-manifest.json --case " + case +
                           " --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR",
                "feedback_command": "cat $OUTPUT/v0001/feedback.json # " + case,
                "test_exit_code": 0, "test_log": "native/" + saved_log.name,
                "test_log_sha256": sha(saved_log),
                "positive_processing_receipt": "native/" + accepted.name,
                "positive_processing_sha256": sha(accepted),
                "missing_source_feedback": "native/" + rejected.name,
                "missing_source_feedback_sha256": sha(rejected),
                "scope": "synthetic saved positive and missing-device negative; original unverified"}}
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
        "status": "selected_cpu_prepared", "cases": entries}
    save(FOLDER / "execution-manifest.json", manifest)
    print(json.dumps({"case_ids": [item["case_id"] for item in entries]}, sort_keys=True))


if __name__ == "__main__":
    main()
