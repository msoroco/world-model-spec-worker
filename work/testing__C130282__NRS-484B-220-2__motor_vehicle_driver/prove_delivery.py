"""Run exact independent positive and missing-map delivery audits for four cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c130282"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if REPO / ".runtime-work" not in Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve().parents:
        raise ValueError("output root must be under .runtime-work")
    rows = []
    script = ROOT / "delivery_audit.py"
    for case in json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))["cases"]:
        cid = case["case_id"]
        tag = cid.split("__")[-1]
        original = SCRATCH / "selected" / tag / "primary" / "compatibility"
        folder = ROOT / "cases" / tag
        positive = SCRATCH / "independent" / ("positive-" + tag + ".json")
        positive.parent.mkdir(parents=True, exist_ok=True)
        positive.unlink(missing_ok=True)
        command = [sys.executable, str(script), "--attempt", str(original),
                   "--case-id", cid, "--output", str(positive), "--diagnostic"]
        done = subprocess.run(command, cwd=REPO, env=os.environ, capture_output=True, text=True)
        positive_log = folder / "proof-delivery-positive.log"
        positive_log.write_text((done.stdout + done.stderr).rstrip() + "\n", encoding="utf-8")
        if done.returncode:
            raise RuntimeError(cid + ": " + positive_log.read_text()[-1500:])
        receipt = folder / "proof-delivery-positive.json"
        receipt.write_bytes(positive.read_bytes())
        negative = SCRATCH / "independent" / ("missing-map-" + tag)
        if negative.exists():
            shutil.rmtree(negative)
        shutil.copytree(original, negative, copy_function=os.link)
        (negative / "original-map.json").unlink()
        negative_output = SCRATCH / "independent" / ("negative-" + tag + ".json")
        negative_output.unlink(missing_ok=True)
        negative_command = [sys.executable, str(script), "--attempt", str(negative),
            "--case-id", cid, "--output", str(negative_output), "--diagnostic"]
        failed = subprocess.run(negative_command, cwd=REPO, env=os.environ,
                                capture_output=True, text=True)
        negative_log = folder / "proof-delivery-negative.log"
        negative_log.write_text((failed.stdout + failed.stderr).rstrip() + "\n", encoding="utf-8")
        if failed.returncode == 0 or "Missing required source: original-map.json" not in negative_log.read_text():
            raise RuntimeError(cid + ": missing original map was not rejected")
        rows.append({"case_id": cid, "positive_exit_code": done.returncode,
            "positive_command": " ".join(command),
            "positive_log": positive_log.relative_to(ROOT).as_posix(),
            "positive_log_sha256": sha(positive_log),
            "positive_receipt": receipt.relative_to(ROOT).as_posix(),
            "positive_receipt_sha256": sha(receipt),
            "negative_exit_code": failed.returncode,
            "negative_command": " ".join(negative_command),
            "negative_log": negative_log.relative_to(ROOT).as_posix(),
            "negative_log_sha256": sha(negative_log),
            "negative_expected_error": "Missing required source: original-map.json"})
        print(tag, "independent delivery positive/negative passed", flush=True)
    (ROOT / "cpu-delivery-proofs.json").write_text(json.dumps(rows, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
