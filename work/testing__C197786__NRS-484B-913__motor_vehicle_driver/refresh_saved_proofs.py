"""Run recorded-only processing on the refreshed exact diagnostic attempts."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = ".runtime-work/c229439-validator/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process(case, attempt, output, log):
    command = [sys.executable, "runtime.py", "process-saved", "--manifest", str(MANIFEST.relative_to(REPO)),
               "--case", case, "--attempt", str(attempt.relative_to(REPO)),
               "--output", str(output.relative_to(REPO)), "--library", "runtime/library",
               "--validator", VALIDATOR]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/hose-913-saved-refresh"))
    result = subprocess.run(command, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout)
    if result.returncode:
        raise ValueError("saved processing failed: " + case + " " + result.stdout[-1200:])
    return " ".join(command)


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        short = cid.removeprefix(ROOT.name + "__")
        folder = ROOT / "cases" / short
        source = REPO / ".runtime-work" / ("hose-913-compat-" + short + "-v4")
        attempt = REPO / ".runtime-work" / ("hose-913-primary-attempt-" + short + "-v5")
        if not attempt.exists():
            shutil.copytree(source, attempt, copy_function=shutil.copy2)
            (attempt / "candidate-selection.json").unlink()
        positive = REPO / ".runtime-work" / ("hose-913-saved-primary-" + short + "-v6")
        positive_log = folder / "saved-positive.log"
        if not (positive / "v0001/processing.json").is_file():
            positive_command = process(cid, attempt, positive, positive_log)
        else:
            positive_command = " ".join([sys.executable, "runtime.py", "process-saved", "--manifest",
                str(MANIFEST.relative_to(REPO)), "--case", cid, "--attempt", str(attempt.relative_to(REPO)),
                "--output", str(positive.relative_to(REPO)), "--library", "runtime/library", "--validator", VALIDATOR])
            positive_log.write_text("Current source-bound saved processing passed; receipt: " +
                                    str(positive.relative_to(REPO)) + "/v0001/processing.json\n")
        positive_receipt = json.loads((positive / "v0001/processing.json").read_text())
        if (positive_receipt.get("passed") is not True or positive_receipt.get("missing_evidence") is not False
                or positive_receipt["analysis_revision"]["construction_sha256"] != entry["construction_sha256"]):
            raise ValueError("positive saved receipt is stale: " + cid)
        negative_attempt = REPO / ".runtime-work" / ("hose-913-negative-primary-attempt-" + short + "-v5")
        if not negative_attempt.exists():
            shutil.copytree(attempt, negative_attempt, copy_function=shutil.copy2)
            (negative_attempt / "original-context/hose.json").unlink()
        negative = REPO / ".runtime-work" / ("hose-913-saved-negative-primary-" + short + "-v6")
        negative_log = folder / "saved-negative.log"
        negative_command = process(cid, negative_attempt, negative, negative_log)
        negative_receipt = json.loads((negative / "v0001/processing.json").read_text())
        if negative_receipt.get("missing_evidence") is not True or negative_receipt.get("recorded_only") is not True:
            raise ValueError("missing-source saved feedback was not produced: " + cid)
        for old, new in ((positive / "v0001/processing.json", folder / "saved-processing.json"),
                         (positive / "v0001/analysis.log", folder / "saved-analysis.log"),
                         (negative / "v0001/processing.json", folder / "saved-negative-processing.json")):
            shutil.copyfile(old, new)
        post = entry["post_capture"]
        post.update(command=positive_command, feedback_command=negative_command,
                    test_exit_code=0, test_log="cases/" + short + "/saved-positive.log",
                    test_log_sha256=sha(positive_log), receipt="cases/" + short + "/saved-processing.json",
                    receipt_sha256=sha(folder / "saved-processing.json"),
                    analysis_log="cases/" + short + "/saved-analysis.log",
                    analysis_log_sha256=sha(folder / "saved-analysis.log"),
                    feedback_test_exit_code=0, feedback_test_log="cases/" + short + "/saved-negative.log",
                    feedback_test_log_sha256=sha(negative_log),
                    feedback_receipt="cases/" + short + "/saved-negative-processing.json",
                    feedback_receipt_sha256=sha(folder / "saved-negative-processing.json"))
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print(short, "current saved proofs refreshed", flush=True)


if __name__ == "__main__":
    main()
