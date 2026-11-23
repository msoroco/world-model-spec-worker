"""Exercise independent exact comparison CLI and wrong-case rejection."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from build_case_plan import PAIRS
from tests.test_comparison_audit import measurement

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    base = REPO / ".runtime-work" / ("c153046-comparison-" +
           datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    base.mkdir(parents=True)
    rows = []
    all_passed = True
    for name, (left_suffix, right_suffix, _) in PAIRS.items():
        folder = base / name
        folder.mkdir()
        left = measurement(folder / "left", left_suffix)
        right = measurement(folder / "right", right_suffix)
        output = folder / "comparison.json"
        command = [sys.executable, str(ROOT / "comparison_audit.py"),
                   "--left", str(left), "--right", str(right),
                   "--comparison", name, "--output", str(output)]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        positive = subprocess.run(command, cwd=REPO, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        passed = positive.returncode == 0 and output.is_file() and json.loads(output.read_text())["passed"] is True
        changed = json.loads(right.read_text())
        changed["case_id"] = "wrong-case"
        right.write_text(json.dumps(changed))
        negative = subprocess.run(command[:-1] + [str(folder / "rejected.json")],
                                  cwd=REPO, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        rejected = negative.returncode != 0 and "comparison case identity" in negative.stdout
        all_passed = all_passed and passed and rejected
        rows.append({"comparison_id": name, "case_ids": [left_suffix, right_suffix],
                     "positive_exit_code": positive.returncode,
                     "comparison_sha256": sha(output) if output.exists() else None,
                     "negative_exit_code": negative.returncode,
                     "negative_expected_error": "comparison case identity",
                     "negative_rejected": rejected,
                     "physical_acceptance_claimed": False})
        print(name, "positive", passed, "wrong-case rejected", rejected)
    receipt = {"format": "c153046-exact-comparison-cpu-proof",
               "all_passed": all_passed, "physical_acceptance_claimed": False,
               "comparisons": rows}
    (ROOT / "cpu-comparison-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
