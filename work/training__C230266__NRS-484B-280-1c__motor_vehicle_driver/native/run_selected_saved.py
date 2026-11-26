"""Reprocess each compatibility fixture without replaying Native capture.

Runs source-complete and missing-review attempts through the public saved-only
entrypoint. Original fixture bytes are compared before and after processing.
"""

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "selected-saved"
MANIFEST = ROOT / "selected-preflight-manifest.json"
COMPAT = ROOT / "compatibility" / "index.json"
INDEX = ROOT / "recorded-only" / "index.json"
VALIDATOR = REPO / ".runtime-work" / "nrs280-decoder" / ".lake" / "build" / "bin" / "adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stage = SCRATCH / (path.name + ".staging")
    stage.write_text(value.rstrip() + "\n")
    os.replace(stage, path)


def output_from_command(command):
    parts = shlex.split(command)
    return Path(parts[parts.index("--output") + 1]).resolve()


def process(case, attempt, output):
    command = [sys.executable, "-B", str(REPO / "runtime.py"), "process-saved",
               "--manifest", str(MANIFEST), "--case", case,
               "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime" / "library"),
               "--validator", str(VALIDATOR)]
    completed = subprocess.run(command, cwd=REPO, capture_output=True,
                               text=True, env=os.environ.copy(), timeout=900)
    if completed.returncode:
        raise RuntimeError(case + " saved-only failed: " + completed.stderr[-1500:])
    receipt = output / "v0001" / "processing.json"
    if not receipt.is_file():
        raise ValueError("Missing public recorded-only receipt: " + case)
    return command, json.loads(receipt.read_text()), receipt


def run_case(entry, compatible):
    case = entry["case_id"]
    suffix = case.rsplit("__", 1)[-1]
    old_receipt = json.loads((ROOT / compatible["receipt"]).read_text())
    if (old_receipt.get("construction_sha256") != entry["construction_sha256"] or
            old_receipt.get("runtime_manifest_sha256") !=
            json.loads(MANIFEST.read_text())["runtime_manifest_sha256"]):
        raise ValueError("Compatibility proof is stale: " + case)
    attempt = output_from_command(compatible["command"])
    if not attempt.is_dir():
        raise ValueError("Missing materialized positive fixture: " + case)
    current_manifest_sha256 = sha(MANIFEST)
    selection_path = attempt / "candidate-selection.json"
    selection = json.loads(selection_path.read_text()) if selection_path.is_file() else {}
    if (selection.get("manifest_sha256") != current_manifest_sha256 or
            selection.get("construction_sha256") != entry["construction_sha256"]):
        raise ValueError("Compatibility fixture binds an old manifest: " + case)
    scope = SCRATCH / (suffix + "-" + entry["construction_sha256"][:10] +
                       "-" + current_manifest_sha256[:10])
    positive = scope / "positive"
    negative = scope / "negative"
    if scope.exists():
        raise ValueError("Use a fresh saved-only proof directory: " + str(scope))
    scope.mkdir(parents=True)
    positive_command, positive_receipt, positive_path = process(case, attempt, positive)
    if not (positive_receipt["passed"] is True and positive_receipt["recorded_only"] is True
            and positive_receipt["missing_evidence"] is False
            and positive_receipt["originals_preserved"] is True):
        raise AssertionError("Positive saved-only proof differs: " + case)
    copied = scope / "negative-attempt"
    shutil.copytree(attempt, copied, copy_function=os.link, symlinks=True)
    (copied / "pedestrian-source-review.jsonl").unlink()
    negative_command, negative_receipt, negative_path = process(case, copied, negative)
    feedback_path = negative / "v0001" / "feedback.json"
    feedback = json.loads(feedback_path.read_text())
    if not (negative_receipt["passed"] is True and negative_receipt["recorded_only"] is True
            and negative_receipt["missing_evidence"] is True
            and negative_receipt["originals_preserved"] is True
            and feedback.get("native_replay_requested") is False
            and "pedestrian-source-review.jsonl" in feedback.get("error", "")):
        raise AssertionError("Missing-source saved-only feedback differs: " + case)
    evidence = ROOT / "recorded-only"
    log_path = evidence / (suffix + "-test.log")
    log_text = (case + "\npositive recorded_only=true, missing_evidence=false, originals_preserved=true\n"
                + "negative recorded_only=true, missing_evidence=true, originals_preserved=true, native_replay_requested=false\n"
                + "positive_receipt_sha256=" + sha(positive_path) + "\n"
                + "negative_receipt_sha256=" + sha(negative_path) + "\n"
                + "feedback_sha256=" + sha(feedback_path))
    atomic(log_path, log_text)
    proof_path = evidence / (suffix + "-proof.json")
    proof = {"format": "worker-nrs280-recorded-only-proof-v1", "case_id": case,
             "construction_sha256": entry["construction_sha256"],
             "manifest_sha256": current_manifest_sha256,
             "positive_command": " ".join(positive_command),
             "negative_command": " ".join(negative_command),
             "positive_receipt_sha256": sha(positive_path),
             "negative_receipt_sha256": sha(negative_path),
             "feedback_sha256": sha(feedback_path),
             "test_exit_code": 0, "test_log": str(log_path.relative_to(ROOT)),
             "test_log_sha256": sha(log_path),
             "positive_missing_evidence": False, "negative_missing_evidence": True,
             "originals_preserved": True, "native_replay_requested": False,
             "scope": "diagnostic saved-only software fixture"}
    atomic(proof_path, json.dumps(proof, indent=2))
    return {"case_id": case, "proof": str(proof_path.relative_to(ROOT)),
            "proof_sha256": sha(proof_path), "construction_sha256": entry["construction_sha256"],
            "manifest_sha256": current_manifest_sha256}


def main():
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["cases"]
    index = json.loads(INDEX.read_text()) if INDEX.is_file() else {
        "format": "worker-nrs280-recorded-only-index-v1", "passed": []}
    passed = {row["case_id"]: row for row in index["passed"]}
    while len(passed) < len(entries):
        compatible = {row["case_id"]: row for row in
                      json.loads(COMPAT.read_text())["passed"]} if COMPAT.is_file() else {}
        progressed = False
        for entry in entries:
            case = entry["case_id"]
            previous = passed.get(case)
            if (previous and previous.get("construction_sha256") == entry["construction_sha256"]
                    and previous.get("manifest_sha256") == sha(MANIFEST)):
                continue
            if case not in compatible:
                continue
            compatibility_receipt = ROOT / compatible[case]["receipt"]
            if not compatibility_receipt.is_file():
                continue
            proven = json.loads(compatibility_receipt.read_text())
            if proven.get("construction_sha256") != entry["construction_sha256"]:
                continue
            attempt = output_from_command(compatible[case]["command"])
            selection_path = attempt / "candidate-selection.json"
            selection = json.loads(selection_path.read_text()) if selection_path.is_file() else {}
            if selection.get("manifest_sha256") != sha(MANIFEST):
                continue
            row = run_case(entry, compatible[case])
            passed[case] = row
            index["passed"] = [passed[name] for name in sorted(passed)]
            atomic(INDEX, json.dumps(index, indent=2))
            print(json.dumps({"case": case.rsplit("__", 1)[-1],
                              "proof_sha256": row["proof_sha256"]}), flush=True)
            progressed = True
        if not progressed:
            time.sleep(5)
    print(json.dumps({"saved_only_passed": len(passed),
                      "index_sha256": sha(INDEX)}), flush=True)


if __name__ == "__main__":
    main()
