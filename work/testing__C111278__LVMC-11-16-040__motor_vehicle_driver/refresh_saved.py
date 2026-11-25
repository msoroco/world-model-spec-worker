"""Run pinned saved-only processing on six synthetic diagnostic acquisitions."""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fresh(base: Path, stem: str) -> Path:
    version = 0
    while True:
        path = base / f"{stem}-{version}"
        if not path.exists():
            return path
        version += 1


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    py = str(REPO / ".venv-cpu/bin/python")
    runtime = str(REPO / "runtime.py")
    validator = str(REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck")
    base = REPO / ".runtime-work/c111278-owner"
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       TMPDIR=str(base / "tmp"),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(base / "pipeline"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        compatible = shlex.split(entry["compatibility"]["command"])
        source = Path(compatible[compatible.index("--output") + 1])
        attempt = fresh(base, f"saved-attempt-{suffix}")
        shutil.copytree(source, attempt)
        (attempt / "candidate-selection.json").unlink(missing_ok=True)
        output = fresh(base, f"saved-processing-{suffix}")
        command = [py, runtime, "process-saved", "--manifest", str(MANIFEST),
                   "--case", entry["case_id"], "--attempt", str(attempt),
                   "--output", str(output), "--library", str(REPO / "runtime/library"),
                   "--validator", validator]
        run = subprocess.run(command, env=environment, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = ROOT / f"saved-{suffix}-positive.log"
        log.write_text("\n".join(line.rstrip() for line in run.stdout.splitlines()).rstrip() + "\n")
        if run.returncode:
            raise RuntimeError(f"{suffix}: {run.stdout[-2500:]}")
        receipt = json.loads((output / "v0001/processing.json").read_text())
        if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
                receipt.get("missing_evidence") is not False or
                receipt.get("originals_preserved") is not True or
                receipt.get("final_video_checks", {}).get("passed") is not True or
                receipt.get("analysis_revision", {}).get("construction_sha256") != entry["construction_sha256"]):
            raise ValueError("saved-only diagnostic receipt incomplete")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json --case {entry['case_id']} --attempt $SAVED_ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator .runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck --owner-release-receipt $OWNER_RELEASE_RECEIPT",
            "feedback_command": f"find $SAVED_OUTPUT -name feedback.json -type f -print # {entry['case_id']}",
            "test_exit_code": 0, "test_log": log.name, "test_log_sha256": sha(log)}
        print(suffix, "saved-only diagnostic passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
