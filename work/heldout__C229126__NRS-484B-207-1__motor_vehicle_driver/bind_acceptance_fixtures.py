"""Bind exact-case positive and stale-pixel-review rejection fixtures."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
OUTPUT = HERE / "acceptance"
SCRIPT = HERE / "acceptance_fixture.py"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    OUTPUT.mkdir(exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        stem = case.rsplit("__", 1)[-1]
        results = {}
        for negative in (False, True):
            label = "negative" if negative else "positive"
            command = [sys.executable, str(SCRIPT), "--case", case]
            if negative:
                command.append("--negative")
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log = OUTPUT / (stem + "-" + label + ".log")
            log.write_text(process.stdout + process.stderr)
            if (negative and (process.returncode == 0 or
                              "Missing, stale, or failed original-pixel review: approach"
                              not in log.read_text()) or
                    not negative and process.returncode != 0):
                raise ValueError("Acceptance fixture failed: " + case + " " + label)
            results[label] = (process.returncode, log)
        pos, neg = results["positive"], results["negative"]
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["held-out"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "command": " ".join([sys.executable, str(SCRIPT), "--case", case]),
            "test_exit_code": pos[0],
            "test_log": str(pos[1].relative_to(HERE)),
            "test_log_sha256": digest(pos[1]),
            "negative_command": " ".join([sys.executable, str(SCRIPT), "--case", case,
                                            "--negative"]),
            "negative_exit_code": neg[0],
            "negative_expected_error": "Missing, stale, or failed original-pixel review: approach",
            "negative_log": str(neg[1].relative_to(HERE)),
            "negative_log_sha256": digest(neg[1]),
            "script": SCRIPT.name, "script_sha256": digest(SCRIPT),
            "fixture_only": True}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("Bound positive and stale-source acceptance checks for", len(manifest["cases"]), "cases")


if __name__ == "__main__":
    main()
