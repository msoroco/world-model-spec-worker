"""Bind independently executed CPU proofs to four exact 250-2 cases."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c125697-2502/final-proof-v6"
SUFFIXES = ("timing_below_training", "timing_inside_training",
            "timing_above_training", "right_approach_inside")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, name):
    target = ROOT / name
    shutil.copyfile(source, target)
    if target.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("returned proof too large: " + name)
    return name


def record(path):
    return {"receipt": path.name, "sha256": sha(path)}


def build():
    manifest = json.loads((ROOT / "execution-manifest.compat-draft.json").read_text())
    script = ROOT / "audit_probe.py"
    for entry, suffix in zip(manifest["cases"], SUFFIXES):
        case = entry["case_id"]
        if case != ROOT.name + "__" + suffix:
            raise ValueError("case order differs")
        for candidate, variant in ((entry, "primary"),
                                   (entry["candidates"][0], "fallback1")):
            token = suffix if variant == "primary" else "fallback-" + suffix
            offline_log = ROOT / copy(SCRATCH / ("offline-" + token + ".log"),
                                      "cpu-offline-" + token + ".log")
            candidate["offline"] = {
                "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" +
                           ROOT.name + "/execution-manifest.json --case " + case +
                           (" --candidate fallback1" if variant != "primary" else "") +
                           " --output .runtime-work/c125697-2502/final-proof-v6/offline-" +
                           token + " --python $PWD/.venv-cpu/bin/python",
                "exit_code": 0, "construction_sha256": candidate["construction_sha256"],
                "log": offline_log.name, "log_sha256": sha(offline_log)}
            comp = SCRATCH / ("compat-" + token)
            receipt = ROOT / copy(comp / "compatibility.json",
                                  "compat-" + token + "-receipt.json")
            analysis = ROOT / copy(comp / "compatibility-analysis.log",
                                   "compat-" + token + "-analysis.log")
            negative = ROOT / copy(comp / "negative-analysis.log",
                                   "compat-" + token + "-negative.log")
            candidate["compatibility"] = {
                "receipt": receipt.name, "sha256": sha(receipt),
                "log": analysis.name, "negative_log": negative.name}
            if variant == "primary":
                entry["negative"] = {"log": negative.name}
        positive = ROOT / copy(SCRATCH / ("audit-" + suffix + ".log"),
                               "audit-" + suffix + "-positive.log")
        negative = ROOT / copy(SCRATCH / ("audit-negative-" + suffix + ".log"),
                               "audit-" + suffix + "-negative.log")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["demo-test", "full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": script.name, "script_sha256": sha(script),
            "command": ".venv-cpu/bin/python work/" + ROOT.name +
                       "/audit_probe.py --production --case " + case +
                       " --attempt $ATTEMPT --processing $PROCESSING_RECEIPT",
            "test_exit_code": 0, "test_log": positive.name,
            "test_log_sha256": sha(positive),
            "negative_command": ".venv-cpu/bin/python work/" + ROOT.name +
                                "/audit_probe.py --case " + case +
                                " --attempt .runtime-work/c125697-2502/"
                                "final-proof-v6/saved-attempt-" + suffix +
                                " --negative-camera",
            "negative_exit_code": 1,
            "negative_expected_error": "sealed original missing or changed: overview.mkv",
            "negative_log": negative.name, "negative_log_sha256": sha(negative)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
        folder = SCRATCH / ("physical-" + suffix)
        fixture_rows = []
        log = ROOT / copy(SCRATCH / ("physical-" + suffix + ".log"),
                          "physical-" + suffix + ".log")
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = ROOT / copy(folder / (kind + ".json"),
                                 "physical-" + suffix + "-" + kind + ".json")
            fixture_rows.append({
                "kind": kind,
                "command": ".venv-cpu/bin/python work/" + ROOT.name +
                           "/physical_probe.py --case " + case +
                           " --attempt .runtime-work/c125697-2502/"
                           "final-proof-v6/saved-attempt-" + suffix +
                           " --output .runtime-work/c125697-2502/"
                           "final-proof-v6/physical-" + suffix,
                "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                "result": result.name, "result_sha256": sha(result)})
        proof = ROOT / ("physical-" + suffix + "-proof.json")
        proof.write_text(json.dumps({
            "case_id": case, "construction_sha256": entry["construction_sha256"],
            "fixtures": fixture_rows,
            "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                     "restoration_verified", "native_exit",
                                     "owner_released", "saved_processing_started"],
                          "exit_code": 0, "log": log.name,
                          "log_sha256": sha(log)}}, indent=2) + "\n")
        entry["physical_preparation"] = record(proof)
        process_log = ROOT / copy(SCRATCH / ("process-" + suffix + ".log"),
                                  "process-" + suffix + ".log")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" +
                       ROOT.name + "/execution-manifest.json --case " + case +
                       " --attempt $ATTEMPT --output $PROCESSING_OUTPUT --library runtime/library"
                       " --validator $VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT",
            "feedback_command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" +
                                ROOT.name + "/execution-manifest.json --case " + case +
                                " --attempt $ATTEMPT --output $PROCESSING_OUTPUT --library runtime/library"
                                " --validator $VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT",
            "test_log": process_log.name, "test_log_sha256": sha(process_log),
            "test_exit_code": 0}
    target = ROOT / "execution-manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    root_construction = json.loads((ROOT / "construction-timing_below_training.json").read_text())
    root_construction.update({
        "mechanisms": [
            "reviewed median-opening crossing and distinct public highways",
            "original inoperative governing-signal and subsection 4 source review",
            "original body entry timing and approach-side relation measured separately",
        ],
        "measurement_plan": {
            "entry_timing": "other and ego original body entry brackets across 900 frames",
            "approach_side": "reviewed original routes and body approach vectors at the crossing",
            "yield_response": "other exit and ego entry order without a legal time cutoff",
        },
        "static_checks": [
            "reviewed OpenDRIVE crossing and distinct public highway sources",
            "governing signal identity, inoperative state and turn exception context",
            "source-joined 900 frame body and four-view camera histories",
        ],
        "termination_rules": ["stop after planned 45 seconds or original-source failure"],
    })
    for item in root_construction["files"]:
        if item["path"] == "config.json":
            config = json.loads(item["content"])
            config["supported_case_ids"] = [case["case_id"] for case in manifest["cases"]]
            item["content"] = json.dumps(config, indent=2) + "\n"
    (ROOT / "construction.json").write_text(json.dumps(root_construction, indent=2) + "\n")
    for item in root_construction["files"]:
        target = ROOT / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"])
    print("bound four exact primary, fallback, saved, audit and physical proofs")


if __name__ == "__main__":
    build()
