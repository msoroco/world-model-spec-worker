"""Exercise exact recorded-only processing on synthetic alley source packets."""
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


def prepare_attempt(source: Path, destination: Path, manifest_sha: str) -> None:
    shutil.copytree(source, destination)
    selection_path = destination / "candidate-selection.json"
    selection = json.loads(selection_path.read_text())
    selection_path.unlink()
    selection["manifest_sha256"] = manifest_sha
    selection_path.write_text(json.dumps(selection, indent=2) + "\n")


def process(case: dict, attempt: Path, output: Path, root: Path) -> tuple[int, Path]:
    owner_receipt = output.parent / (output.name + "-synthetic-release.json")
    owner_receipt.write_text(json.dumps({
        "event": "owner_released", "operator_attested": True,
        "native_construction_sha256": sha(attempt / "construction.json"),
        "native_exit_sha256": None, "no_resource_operation_performed": True,
        "diagnostic_fixture": True,
    }) + "\n")
    environment = dict(os.environ)
    environment.update(ATTEMPT=str(attempt), PROCESSED=str(output),
                       LEAN_VALIDATOR=str(REPO / ".runtime-work/c229404-owner-nov26/validator" /
                                          ".lake/build/bin/adapterCheck"),
                       OWNER_RELEASE_RECEIPT=str(owner_receipt),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(root / "pipeline-output"),
                       TMPDIR=str(root / "tmp"))
    (root / "pipeline-output").mkdir(exist_ok=True)
    (root / "tmp").mkdir(exist_ok=True)
    completed = subprocess.run(case["post_capture"]["command"], shell=True, cwd=REPO,
                               env=environment, capture_output=True, text=True, check=False)
    return completed.returncode, output / "v0001"


def main() -> None:
    manifest_path = PACKAGE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    scratch = REPO / ".runtime-work"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c229404-saved-", dir=scratch) as directory:
        root = Path(directory)
        for case in manifest["cases"]:
            case_id = case["case_id"]
            suffix = case_id.removeprefix(manifest["assignment_id"] + "__")
            assert case["post_capture"]["recorded_only"] is True
            assert case["post_capture"]["command"] == case["post_capture"]["feedback_command"]
            source = scratch / "c229404-proof-v5" / ("compat-" + suffix + "-primary")
            positive_attempt = root / suffix / "positive-original"
            prepare_attempt(source, positive_attempt, sha(manifest_path))
            positive_exit, positive = process(case, positive_attempt,
                                              root / suffix / "positive-processed", root)
            positive_receipt = positive / "processing.json"
            assert positive_exit == 0 and positive_receipt.is_file(), case_id
            result = json.loads(positive_receipt.read_text())
            assert result["case_id"] == case_id and result["passed"] is True
            assert result["recorded_only"] is True and result["originals_preserved"] is True
            assert result["missing_evidence"] is False
            assert result["physical_acceptance_claimed"] is False

            negative_attempt = root / suffix / "missing-source-original"
            prepare_attempt(source, negative_attempt, sha(manifest_path))
            (negative_attempt / "original-attempt/alley_geometry.json").unlink()
            negative_exit, negative = process(case, negative_attempt,
                                              root / suffix / "negative-processed", root)
            feedback_path = negative / "feedback.json"
            assert feedback_path.is_file(), (case_id, negative_exit)
            feedback = json.loads(feedback_path.read_text())
            assert feedback["recorded_only"] is True
            assert feedback["native_replay_requested"] is False
            assert "Missing required source: original-attempt/alley_geometry.json" in feedback["error"]
            negative_receipt = negative / "processing.json"
            if negative_receipt.is_file():
                incomplete = json.loads(negative_receipt.read_text())
                assert incomplete["case_id"] == case_id and incomplete["missing_evidence"] is True
            else:
                assert negative_exit != 0 and feedback["case_id"] == case_id
            print(suffix + ": saved-only success and missing-source feedback verified")


if __name__ == "__main__":
    main()
