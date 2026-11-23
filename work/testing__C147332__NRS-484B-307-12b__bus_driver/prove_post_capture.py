"""Prove exact saved-only processing after freezing the current manifest bytes."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
MANIFEST = PACKAGE / "execution-manifest.json"
VALIDATOR = ROOT / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"
SCRATCH = ROOT / ".runtime-work/c147332-nov24"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(command: list[str], log: Path) -> None:
    with log.open("x") as output:
        result = subprocess.run(command, cwd=ROOT, env=os.environ,
                                stdout=output, stderr=subprocess.STDOUT,
                                timeout=600, check=False)
    if result.returncode:
        raise RuntimeError(f"{log.name} exited {result.returncode}")


def main() -> None:
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not output_root.is_relative_to((ROOT / ".runtime-work").resolve()):
        raise ValueError("runtime output root must be under .runtime-work")
    frozen = digest(MANIFEST)
    manifest = json.loads(MANIFEST.read_text())
    for case in manifest["cases"]:
        case_id = case["case_id"]
        kind = case_id.rsplit("__", 1)[1]
        if kind == "adjacent_travel":
            attempt = ROOT / ".runtime-work/c147332-nov24-compat/adjacent_travel"
            if json.loads((attempt / "candidate-selection.json").read_text())["manifest_sha256"] != frozen:
                raise ValueError("adjacent attempt no longer binds frozen manifest")
        else:
            attempt = SCRATCH / "compat" / kind
            checked([sys.executable, str(ROOT / "runtime.py"), "compatibility",
                     "--manifest", str(MANIFEST), "--case", case_id,
                     "--candidate", "primary", "--output", str(attempt),
                     "--library", str(ROOT / "runtime/library"),
                     "--validator", str(VALIDATOR)],
                    PACKAGE / f"nov24-{kind}-compat.log")
        saved = SCRATCH / "saved" / kind
        checked([sys.executable, str(ROOT / "runtime.py"), "process-saved",
                 "--manifest", str(MANIFEST), "--case", case_id,
                 "--attempt", str(attempt), "--output", str(saved),
                 "--library", str(ROOT / "runtime/library"),
                 "--validator", str(VALIDATOR)],
                PACKAGE / f"nov24-{kind}-saved.log")
        receipt = json.loads((PACKAGE / f"nov24-{kind}-saved.log").read_text())
        if (receipt.get("passed") is not True or
                receipt.get("recorded_only") is not True or
                receipt.get("case_id") != case_id or
                receipt.get("missing_evidence") is not False or
                receipt.get("physical_acceptance_claimed") is not False):
            raise ValueError("saved processing did not prove recorded-only analysis")
        if digest(MANIFEST) != frozen:
            raise ValueError("manifest changed during saved proof")
        print(f"{kind}: source-bound diagnostic saved processing passed", flush=True)


if __name__ == "__main__":
    main()
