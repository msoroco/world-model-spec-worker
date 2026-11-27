"""Bind executed saved-only CPU processing receipts to exact left-turn cases."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PRIVATE = REPO / ".runtime-work/c178244-nov26"
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        tag = case.rsplit("__", 1)[-1]
        attempt = PRIVATE / ("saved-compat-" + tag + "-reviewed2")
        output = PRIVATE / ("saved-" + tag + "-reviewed2")
        source = output / "v0001/processing.json"
        proof = json.loads(source.read_text())
        if not (proof.get("case_id") == case and proof.get("recorded_only") is True
                and proof.get("passed") is True and proof.get("missing_evidence") is False
                and proof.get("originals_preserved") is True
                and proof.get("final_video_checks", {}).get("passed") is True):
            raise ValueError("saved-only proof incomplete: " + tag)
        if digest(attempt / "construction.json") != entry["construction_sha256"]:
            raise ValueError("saved-only attempt has stale construction: " + tag)
        target = ROOT / "cases" / tag / "saved-processing.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
        command = (
            f"{REPO / '.venv-cpu/bin/python'} {REPO / 'runtime.py'} process-saved "
            f"--manifest {MANIFEST} --case {case} --attempt {attempt} --output {output} "
            f"--library {REPO / 'runtime/library'} --validator {VALIDATOR}"
        )
        entry["post_capture"] = {
            "recorded_only": True,
            "command": command,
            "feedback_command": f'cat "{output}/feedback.json"',
            "test_log": target.relative_to(ROOT).as_posix(),
            "test_log_sha256": digest(target),
            "test_exit_code": 0,
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
