"""Exercise independent delivery and physical-outcome checkers per exact case."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
SCRIPT = HERE / "acceptance_fixture.py"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    output = HERE / "acceptance"
    output.mkdir(exist_ok=True)
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.split("__")[-1]
        command = [".venv-cpu/bin/python", SCRIPT.relative_to(ROOT).as_posix(),
                   "--case", case]
        positive = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        positive_log = output / (suffix + "-positive.log")
        positive_log.write_text(positive.stdout + positive.stderr)
        if positive.returncode:
            raise ValueError(case + " independent positive fixture failed: " + positive_log.read_text()[-1000:])
        negative_command = command + ["--negative"]
        negative = subprocess.run(negative_command, cwd=ROOT, capture_output=True, text=True)
        negative_log = output / (suffix + "-negative.log")
        negative_log.write_text(negative.stdout + negative.stderr)
        expected = "Missing, stale, or failed original-pixel review"
        if negative.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError(case + " independent negative fixture did not reject stale pixels")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["held-out"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "command": " ".join(command), "test_exit_code": 0,
            "test_log": positive_log.relative_to(HERE).as_posix(),
            "test_log_sha256": digest(positive_log),
            "negative_command": " ".join(negative_command),
            "negative_exit_code": negative.returncode,
            "negative_expected_error": "stale",
            "negative_log": negative_log.relative_to(HERE).as_posix(),
            "negative_log_sha256": digest(negative_log),
            "script": "acceptance_fixture.py", "script_sha256": digest(SCRIPT),
            "fixture_only": True,
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print(suffix, "independent positive and stale-pixel rejection passed", flush=True)


if __name__ == "__main__":
    main()
