"""Bind successful recorded-only diagnostic processing receipts by exact case."""

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for case in manifest["cases"]:
        short = case["case_id"].removeprefix(ROOT.name + "__")
        source = REPO / ".runtime-work" / ("hose-913-saved-primary-" + short + "-v4")
        processing = source / "v0001/processing.json"
        receipt = json.loads(processing.read_text())
        if (receipt.get("case_id") != case["case_id"] or receipt.get("passed") is not True
                or receipt.get("recorded_only") is not True
                or receipt.get("originals_preserved") is not True
                or receipt.get("missing_evidence") is not False
                or receipt.get("analysis_revision", {}).get("construction_sha256")
                != case["construction_sha256"]):
            raise ValueError("selected saved-processing proof incomplete: " + short)
        folder = ROOT / "cases" / short
        copies = {processing: folder / "saved-processing.json",
                  source / "v0001/analysis.log": folder / "saved-analysis.log",
                  REPO / ".runtime-work" / ("hose-913-saved-primary-" + short + "-v4-stdout.log"):
                      folder / "saved-positive.log"}
        for old, new in copies.items():
            shutil.copyfile(old, new)
        command = (".venv-cpu/bin/python runtime.py process-saved --manifest work/" + ROOT.name +
                   "/execution-manifest.json --case " + case["case_id"] + " --attempt .runtime-work/" +
                   "hose-913-primary-attempt-" + short + "-v4 --output .runtime-work/" +
                   "hose-913-saved-primary-" + short + "-v4 --library runtime/library --validator " +
                   ".runtime-work/c229439-validator/.lake/build/bin/adapterCheck")
        case["post_capture"] = {
            "recorded_only": True, "command": command,
            "feedback_command": command.replace("hose-913-primary-attempt-", "hose-913-negative-primary-attempt-").replace(
                "hose-913-saved-primary-", "hose-913-saved-negative-primary-"),
            "test_exit_code": 0,
            "test_log": str((folder / "saved-positive.log").relative_to(ROOT)),
            "test_log_sha256": sha(folder / "saved-positive.log"),
            "receipt": str((folder / "saved-processing.json").relative_to(ROOT)),
            "receipt_sha256": sha(folder / "saved-processing.json"),
            "analysis_log": str((folder / "saved-analysis.log").relative_to(ROOT)),
            "analysis_log_sha256": sha(folder / "saved-analysis.log"),
        }
        print(short, "saved-only passed")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
