"""Check exact saved-only receipts and exercise each current feedback command."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((PACKAGE / "execution-manifest.json").read_text())
    scratch = REPO / ".runtime-work"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c111329-post-capture-", dir=scratch) as directory:
        root = Path(directory)
        for case in manifest["cases"]:
            case_id = case["case_id"]
            suffix = case_id.removeprefix(manifest["assignment_id"] + "__")
            post = case["post_capture"]
            positive = PACKAGE / post["test_log"]
            negative = PACKAGE / post["feedback_test_log"]
            saved = json.loads(positive.read_text())
            source_feedback = json.loads(negative.read_text())
            assert sha(positive) == post["test_log_sha256"]
            assert sha(negative) == post["feedback_test_log_sha256"]
            assert saved["case_id"] == case_id and saved["passed"] is True
            assert saved["recorded_only"] is True and saved["missing_evidence"] is False
            assert saved["originals_preserved"] is True
            assert source_feedback["recorded_only"] is True
            assert source_feedback["native_replay_requested"] is False
            assert "Missing required source: effective-site-packet.json" in source_feedback["error"]
            assert post["command"] == post["feedback_command"]

            # Rebind only a copied synthetic selection receipt to the current
            # manifest; the retained acquisition and prior proofs stay intact.
            source = scratch / ("c111329-287-1c-compat-v11-" + suffix + "-primary")
            diagnostic_attempt = root / suffix / "diagnostic-original"
            shutil.copytree(source, diagnostic_attempt)
            selection_path = diagnostic_attempt / "candidate-selection.json"
            selection = json.loads(selection_path.read_text())
            selection_path.unlink()
            selection["manifest_sha256"] = sha(PACKAGE / "execution-manifest.json")
            selection_path.write_text(json.dumps(selection, indent=2) + "\n")
            owner_receipt = root / suffix / "synthetic-owner-release.json"
            owner_receipt.write_text(json.dumps({
                "event": "owner_released", "operator_attested": True,
                "native_construction_sha256": sha(diagnostic_attempt / "construction.json"),
                "native_exit_sha256": None, "no_resource_operation_performed": True,
                "diagnostic_fixture": True,
            }) + "\n")
            success_output = root / suffix / "successful-processing"
            success_env = dict(os.environ)
            success_env.update(ATTEMPT=str(diagnostic_attempt),
                               PROCESSED=str(success_output),
                               LEAN_VALIDATOR=str(scratch / "c111329-287-1c-decoder" /
                                                  ".lake/build/bin/adapterCheck"),
                               OWNER_RELEASE_RECEIPT=str(owner_receipt),
                               SCENARIO_PIPELINE_OUTPUT_ROOT=str(root / "pipeline-output"))
            success = subprocess.run(post["command"], shell=True, cwd=REPO,
                                     env=success_env, capture_output=True,
                                     text=True, check=False)
            success_receipt = success_output / "v0001" / "processing.json"
            if success.returncode != 0 or not success_receipt.is_file():
                raise AssertionError("Bound saved command failed on diagnostic source: " +
                                     case_id + " " + success.stderr[-400:])
            actual = json.loads(success_receipt.read_text())
            assert actual["case_id"] == case_id and actual["passed"] is True
            assert actual["recorded_only"] is True and actual["originals_preserved"] is True
            assert actual["missing_evidence"] is False

            attempt = root / suffix / "empty-original"
            attempt.mkdir(parents=True)
            output = root / suffix / "processed"
            environment = dict(os.environ)
            environment.update(ATTEMPT=str(attempt), PROCESSED=str(output),
                               LEAN_VALIDATOR="/bin/true",
                               OWNER_RELEASE_RECEIPT=str(root / suffix / "owner-release.json"),
                               SCENARIO_PIPELINE_OUTPUT_ROOT=str(root / "pipeline-output"))
            process = subprocess.run(post["feedback_command"], shell=True, cwd=REPO,
                                     env=environment, capture_output=True, text=True, check=False)
            feedback_path = output / "v0001" / "feedback.json"
            assert process.returncode != 0 and feedback_path.is_file()
            feedback = json.loads(feedback_path.read_text())
            assert feedback["case_id"] == case_id
            assert feedback["recorded_only"] is True
            assert feedback["native_replay_requested"] is False
            assert feedback["error_type"] == "FileNotFoundError" and feedback["error"]
            print(suffix + ": exact saved command succeeds on synthetic source; "
                  "missing-source and case-specific failure feedback verified")


if __name__ == "__main__":
    main()
