"""Run both sides of each exact selected comparison CPU isolation proof."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
PYTHON = ROOT / ".venv-cpu/bin/python"
SCRIPT = FOLDER / "comparison_audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((FOLDER / "case-plan.json").read_text())
    directory = FOLDER / "comparison-proof"
    directory.mkdir(exist_ok=True)
    receipts = {}
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        suffix = ident.removeprefix(FOLDER.name + "__")
        positive = directory / (suffix + "-positive.log")
        negative = directory / (suffix + "-negative.log")
        base = [str(PYTHON), str(SCRIPT), "--comparison", ident]
        for command, output, should_pass in ((base, positive, True),
                                             (base + ["--negative"], negative, False)):
            with output.open("wb") as log:
                run = subprocess.run(command, cwd=ROOT,
                                     env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                                          "TMPDIR": str(ROOT / ".runtime-work/c150660-tmp")},
                                     stdout=log, stderr=subprocess.STDOUT)
            if (run.returncode == 0) != should_pass:
                raise ValueError("Comparison predicate differs: " + ident)
        if "Comparison fixed condition changed: camera_plan" not in negative.read_text():
            raise ValueError("Changed comparison condition was accepted: " + ident)
        receipts[ident] = {"format": "worker-comparison-proof", "comparison_id": ident,
                           "case_ids": comparison["case_ids"], "script": "comparison_audit.py",
                           "script_sha256": sha(SCRIPT), "positive_exit_code": 0,
                           "negative_exit_code": 1,
                           "positive_log": "comparison-proof/" + positive.name,
                           "positive_log_sha256": sha(positive),
                           "negative_log": "comparison-proof/" + negative.name,
                           "negative_log_sha256": sha(negative)}
    (directory / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    return len(receipts)


if __name__ == "__main__":
    print(build())
