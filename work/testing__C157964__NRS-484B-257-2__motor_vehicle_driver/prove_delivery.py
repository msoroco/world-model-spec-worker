"""Bind six exact selected delivery audits and source-corruption rejections."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c157964-nov27"
AUDIT = ROOT / "delivery_audit.py"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH))
    result = subprocess.run(command, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout.rstrip("\n") + "\n")
    return result.returncode


def main():
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        stage = SCRATCH / ("saved-proof-" + suffix + "-v3/v0001/analysis")
        output = ROOT / ("selected-delivery-audit-" + suffix + ".json")
        if output.exists():
            output.unlink()
        command = [sys.executable, str(AUDIT), "--stage", str(stage), "--case", case,
                   "--diagnostic-fixture", "--output", str(output)]
        positive = ROOT / ("cpu-delivery-" + suffix + "-positive.log")
        if run(command, positive) or not output.is_file():
            raise ValueError("selected delivery positive audit failed: " + positive.read_text()[-1400:])
        audited = json.loads(output.read_text())
        if audited.get("case_id") != case or audited.get("checks") != CHECKS or \
                audited.get("physical_acceptance_claimed") is not False:
            raise ValueError("selected delivery audit content differs")
        corrupt = SCRATCH / ("delivery-corrupt-" + suffix + "-v1")
        if corrupt.exists():
            shutil.rmtree(corrupt)
        shutil.copytree(stage, corrupt)
        original = corrupt / "original-attempt/history.json"
        original.write_text(original.read_text().replace('"case_id":', '"tampered_case_id":', 1))
        negative_output = SCRATCH / ("delivery-rejected-" + suffix + "-v1.json")
        if negative_output.exists():
            negative_output.unlink()
        negative_command = [sys.executable, str(AUDIT), "--stage", str(corrupt),
                            "--case", case, "--diagnostic-fixture", "--output",
                            str(negative_output)]
        negative = ROOT / ("cpu-delivery-" + suffix + "-negative.log")
        negative_code = run(negative_command, negative)
        error = "sealed original source changed"
        if negative_code == 0 or error not in negative.read_text() or negative_output.exists():
            raise ValueError("selected delivery source-corruption rejection failed")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["demo-test", "full-test"], "checks": CHECKS,
            "script": "delivery_audit.py", "script_sha256": sha(AUDIT),
            "command": " ".join(command), "test_exit_code": 0,
            "test_log": positive.name, "test_log_sha256": sha(positive),
            "negative_command": " ".join(negative_command),
            "negative_exit_code": negative_code, "negative_expected_error": error,
            "negative_log": negative.name, "negative_log_sha256": sha(negative),
            "diagnostic_audit": output.name, "diagnostic_audit_sha256": sha(output),
            "physical_acceptance_claimed": False}
        print("selected delivery audit passed", suffix, flush=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
