"""Bind independent selected-case positive and missing-source rejection proofs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
SCRATCH = REPO / ".runtime-work/c229831-temp"
MANIFEST = FOLDER / "execution-manifest.json"
SCRIPT = FOLDER / "delivery_acceptance.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(case, attempt, output):
    return [sys.executable, str(SCRIPT), "--attempt", str(attempt),
            "--case", case, "--output", str(output), "--diagnostic"]


def main():
    manifest = json.loads(MANIFEST.read_text())
    count = 0
    for entry in manifest["cases"]:
        case = entry["case_id"]
        label = case.rsplit("_", 1)[-1]
        source = SCRATCH / f"compat-{label}-primary-v2"
        target = FOLDER / "proofs" / label / "primary"
        target.mkdir(parents=True, exist_ok=True)
        negative = SCRATCH / f"delivery-negative-{label}"
        negative.mkdir(parents=True, exist_ok=True)
        for path in source.iterdir():
            if path.name == "rider_arm.jsonl":
                continue
            link = negative / path.name
            if not link.exists() and not link.is_symlink():
                link.symlink_to(path.resolve(), target_is_directory=path.is_dir())
        positive_command = command(case, source, target / "delivery-audit.json")
        negative_command = command(case, negative, SCRATCH / f"delivery-rejected-{label}.json")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        positive = subprocess.run(positive_command, env=env, capture_output=True, text=True)
        negative_run = subprocess.run(negative_command, env=env, capture_output=True, text=True)
        positive_log = target / "delivery-positive.log"
        negative_log = target / "delivery-negative.log"
        positive_log.write_text((positive.stdout + positive.stderr).strip() + "\n")
        negative_log.write_text((negative_run.stdout + negative_run.stderr).strip() + "\n")
        expected = "Missing delivery source: rider_arm.jsonl"
        if positive.returncode != 0 or negative_run.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError("Independent delivery positive/negative proof failed")
        audit = json.loads((target / "delivery-audit.json").read_text())
        if audit["case_id"] != case or audit["frames"] != 600 or not audit["diagnostic_fixture"]:
            raise ValueError("Independent delivery audit differs")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"],
            "checks": audit["checks"],
            "script": SCRIPT.relative_to(FOLDER).as_posix(),
            "script_sha256": sha(SCRIPT),
            "command": " ".join(positive_command),
            "test_exit_code": positive.returncode,
            "test_log": positive_log.relative_to(FOLDER).as_posix(),
            "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(negative_command),
            "negative_exit_code": negative_run.returncode,
            "negative_expected_error": expected,
            "negative_log": negative_log.relative_to(FOLDER).as_posix(),
            "negative_log_sha256": sha(negative_log)}
        count += 1
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"exact_independent_delivery_audits": count,
                      "diagnostic_fixture": True, "physical_acceptance": False}))


if __name__ == "__main__":
    main()
