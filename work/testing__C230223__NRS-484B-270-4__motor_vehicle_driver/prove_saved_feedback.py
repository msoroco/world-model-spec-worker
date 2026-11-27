"""Exercise the exact saved-processing feedback commands without Native replay."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]


def main() -> None:
    manifest = json.loads((PACKAGE / "execution-manifest.json").read_text())
    scratch = REPO / ".runtime-work"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c230223-feedback-", dir=scratch) as directory:
        root = Path(directory)
        for case in manifest["cases"]:
            case_id = case["case_id"]
            suffix = case_id.removeprefix(manifest["assignment_id"] + "__")
            attempt = root / suffix / "empty-original"
            attempt.mkdir(parents=True)
            output = root / suffix / "processed"
            environment = dict(os.environ)
            environment.update(ATTEMPT=str(attempt), PROCESSED=str(output),
                               LEAN_VALIDATOR="/bin/true",
                               OWNER_RELEASE_RECEIPT=str(root / suffix / "owner-release.json"),
                               SCENARIO_PIPELINE_OUTPUT_ROOT=str(root / "pipeline-output"))
            command = case["post_capture"]["feedback_command"]
            process = subprocess.run(command, shell=True, cwd=REPO, env=environment,
                                     capture_output=True, text=True, check=False)
            feedback_file = output / "v0001" / "feedback.json"
            if process.returncode == 0 or not feedback_file.is_file():
                raise AssertionError("Saved processor failed to emit feedback: " + case_id)
            feedback = json.loads(feedback_file.read_text())
            if (feedback.get("case_id") != case_id or feedback.get("recorded_only") is not True or
                    feedback.get("native_replay_requested") is not False or
                    feedback.get("error_type") != "FileNotFoundError" or
                    not feedback.get("error")):
                raise AssertionError("Feedback does not identify the failed saved case: " + case_id)
            print(suffix + ": recorded-only case-bound feedback on missing original source")


if __name__ == "__main__":
    main()
