"""Bind positive and rejected original-source delivery audit predicates per case."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from case_specs import CASES

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
SCRIPT = FOLDER / "delivery_audit.py"
PYTHON = ROOT / ".venv-cpu/bin/python"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    folder = FOLDER / "delivery-proof"
    folder.mkdir(exist_ok=True)
    receipts = {}
    for suffix in CASES:
        case = FOLDER.name + "__" + suffix
        positive = folder / (suffix + "-positive.log")
        negative = folder / (suffix + "-negative.log")
        base = [str(PYTHON), str(SCRIPT), "--case", case, "--self-test"]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
               "TMPDIR": str(ROOT / ".runtime-work/c150660-tmp")}
        for command, log, expected in ((base, positive, 0),
                                        (base + ["--negative"], negative, 1)):
            with log.open("wb") as out:
                run = subprocess.run(command, cwd=ROOT, env=env, stdout=out,
                                     stderr=subprocess.STDOUT)
            if (run.returncode == 0) != (expected == 0):
                raise ValueError("Delivery predicate result differs: " + case)
        if "Missing original source: exact Native result" not in negative.read_text():
            raise ValueError("Delivery negative source was accepted: " + case)
        receipts[suffix] = {
            "case_id": case, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "test_exit_code": 0, "negative_exit_code": 1,
            "negative_expected_error": "Missing original source: exact Native result",
            "command": ".venv-cpu/bin/python work/" + FOLDER.name +
                       "/delivery_audit.py --case " + case + " --self-test",
            "negative_command": ".venv-cpu/bin/python work/" + FOLDER.name +
                                "/delivery_audit.py --case " + case +
                                " --self-test --negative",
            "script": "delivery_audit.py", "script_sha256": sha(SCRIPT),
            "test_log": "delivery-proof/" + positive.name,
            "test_log_sha256": sha(positive),
            "negative_log": "delivery-proof/" + negative.name,
            "negative_log_sha256": sha(negative),
        }
    (folder / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    return len(receipts)


if __name__ == "__main__":
    print(build())
