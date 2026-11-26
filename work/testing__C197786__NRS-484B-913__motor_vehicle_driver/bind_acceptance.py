"""Run exact synthetic acceptance checks and bind their proof logs."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRIPT = "work/" + ROOT.name + "/acceptance_fixture.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.removeprefix(ROOT.name + "__")
        folder = ROOT / "cases" / short
        attempt = ".runtime-work/hose-913-primary-attempt-" + short + "-v4"
        output = ".runtime-work/hose-913-acceptance/" + short + ".json"
        passage = "avoid" if short.endswith("_avoid") else "cross"
        common = [sys.executable, SCRIPT, "--case", case, "--attempt", attempt,
                  "--output", output, "--expected-passage", passage]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/hose-913-acceptance"))
        checks = []
        for negative in (False, True):
            command = common + (["--negative-missing-video"] if negative else [])
            log = folder / ("acceptance-negative.log" if negative else "acceptance-positive.log")
            run = subprocess.run(command, cwd=REPO, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write_text(run.stdout)
            if negative:
                if run.returncode == 0 or "original video source missing" not in run.stdout:
                    raise ValueError("missing-video negative audit failed: " + case)
            elif run.returncode != 0:
                raise ValueError("positive synthetic audit failed: " + case + " " + run.stdout)
            checks.append((" ".join(command), run.returncode, log))
        positive, negative = checks
        entry["delivery_acceptance"].update({
            "script": SCRIPT.removeprefix("work/" + ROOT.name + "/"),
            "script_sha256": sha(ROOT / "acceptance_fixture.py"),
            "command": positive[0], "test_exit_code": 0,
            "test_log": str(positive[2].relative_to(ROOT)),
            "test_log_sha256": sha(positive[2]),
            "negative_command": negative[0], "negative_exit_code": negative[1],
            "negative_expected_error": "original video source missing",
            "negative_log": str(negative[2].relative_to(ROOT)),
            "negative_log_sha256": sha(negative[2]),
            "scope": "synthetic source and full pixel-buffer decode; physical visibility unreviewed",
        })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(len(manifest["cases"]), "exact synthetic acceptance proofs bound")


if __name__ == "__main__":
    main()
