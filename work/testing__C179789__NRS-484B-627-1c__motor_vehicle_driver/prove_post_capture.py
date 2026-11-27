"""Exercise exact manifest saved-only commands on source-shaped diagnostics."""

import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRIVATE = REPO / ".runtime-work/c179789-owner/output"
PROOF = REPO / ".runtime-work/c179789-owner/post-capture-nov27"
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"


def main():
    manifest = json.loads(MANIFEST.read_text())
    PROOF.mkdir(parents=True, exist_ok=True)
    assert VALIDATOR.is_file()
    for entry in manifest["cases"]:
        case = entry["case_id"]
        tag = case.rsplit("__", 1)[-1]
        source = PRIVATE / ("saved-compat-" + tag + "-v2")
        attempt = PROOF / (tag + "-attempt")
        assert source.is_dir() and not attempt.exists(), tag
        shutil.copytree(source, attempt, copy_function=os.link)
        (attempt / "candidate-selection.json").unlink(missing_ok=True)
        assert json.loads((attempt / "construction.json").read_text()) == json.loads((HERE / entry["construction"]).read_text()), tag
        for negative in (False, True):
            output = PROOF / (tag + ("-missing-validator" if negative else "-positive"))
            env = dict(os.environ)
            env.update(ATTEMPT=str(attempt), SAVED_OUTPUT=str(output),
                       LIBRARY=str(REPO / "runtime/library"),
                       VALIDATOR=str(PROOF / "missing-validator") if negative else str(VALIDATOR),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(PROOF), TMPDIR=str(PROOF),
                       PYTHONDONTWRITEBYTECODE="1")
            actual = entry["post_capture"]["feedback_command" if negative else "command"]
            run = subprocess.run(actual, shell=True, cwd=REPO, env=env,
                                 capture_output=True, text=True, timeout=300)
            version = output / "v0001"
            if negative:
                assert run.returncode != 0, tag + " accepted missing validator"
                feedback = json.loads((version / "feedback.json").read_text())
                assert feedback["case_id"] == case and feedback["recorded_only"] is True
                assert feedback["native_replay_requested"] is False and feedback.get("error")
                assert "validator" in feedback["error"].lower(), feedback
                print(tag + ": missing validator rejected with saved feedback", flush=True)
            else:
                assert run.returncode == 0, tag + ": " + (run.stdout + run.stderr)[-1500:]
                receipt = json.loads((version / "processing.json").read_text())
                assert receipt["case_id"] == case and receipt["passed"] is True
                assert receipt["recorded_only"] is True and receipt["originals_preserved"] is True
                assert receipt["missing_evidence"] is False
                assert receipt["final_video_checks"]["passed"] is True
                print(tag + ": source-shaped saved processing passed", flush=True)
    print("Diagnostic software proof only; physical and legal acceptance remain unconfirmed", flush=True)


if __name__ == "__main__":
    main()
