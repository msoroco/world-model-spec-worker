"""Bind exact positive/negative independent audit protocol proofs."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.draft.json"
PYTHON = ROOT / ".venv-cpu/bin/python"


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def proof(command, log, env):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    content = "\n".join(line.rstrip() for line in result.stdout.rstrip().splitlines())
    log.write_text(content + "\n" if content else "", encoding="utf-8")
    return result.returncode


def main():
    env = dict(os.environ)
    scratch = ROOT / ".runtime-work/c412982-lvmc180-owner"
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(scratch / "output")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(ROOT / "runtime/scenario_pipeline")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        slug = cid.removeprefix(HERE.name + "__")
        saved_root = scratch / "lifecycle-v1/saved" / slug
        base = [PYTHON, HERE / "delivery_probe.py", "--case", cid,
                "--saved-root", saved_root]
        positive = base + ["--mode", "positive"]
        negative = base + ["--mode", "missing_source"]
        positive_log = HERE / ("proof-delivery-positive-" + slug + ".log")
        negative_log = HERE / ("proof-delivery-negative-" + slug + ".log")
        success = proof(positive, positive_log, env)
        rejection = proof(negative, negative_log, env)
        if success != 0 or rejection != 2:
            raise ValueError("delivery protocol proof failed: " + slug)
        entry["delivery_acceptance"] = {
            "case_id": cid, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "cpu_proof_kind": "mock_only_contract_wiring",
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": " ".join(str(x) for x in positive),
            "test_exit_code": success, "test_log": positive_log.name,
            "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(str(x) for x in negative),
            "negative_exit_code": rejection,
            "negative_expected_error": "sealed original missing or changed: fremont-site.json",
            "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log)}
        print("passed", slug, "independent audit protocol positive and negative", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
