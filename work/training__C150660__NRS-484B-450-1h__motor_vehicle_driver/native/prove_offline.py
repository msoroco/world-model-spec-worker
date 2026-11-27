"""Run pinned offline construction check for all exact primary/fallback bundles."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from case_specs import CASES

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
PYTHON = str((ROOT / ".venv-cpu/bin/python").resolve())
MANIFEST = FOLDER / "draft-construction-manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest():
    rows = []
    for suffix in CASES:
        case = FOLDER.name + "__" + suffix
        primary = FOLDER / "cases" / suffix / "primary/construction.json"
        fallback = FOLDER / "cases" / suffix / "fallback1/construction.json"
        rows.append({"case_id": case,
                     "construction": str(primary.relative_to(FOLDER)),
                     "construction_sha256": digest(primary),
                     "measurement_procedure": {"entrypoint": "finalize.py"},
                     "measurement_contract": "cases/" + suffix + "/measurement-contract.json",
                     "fixture_recipe": "work/" + FOLDER.name + "/native/diagnostic/" + suffix + "/fixture-recipe.json",
                     "candidates": [{"id": "fallback1",
                                     "construction": str(fallback.relative_to(FOLDER)),
                                     "construction_sha256": digest(fallback)}]})
    MANIFEST.write_text(json.dumps({"format": "worker-construction-draft",
                                    "delivery_readiness_claimed": False,
                                    "runtime_manifest_sha256": digest(ROOT / "runtime/SOURCE-MANIFEST.json"),
                                    "cases": rows}, indent=2) + "\n")
    return rows


if __name__ == "__main__":
    rows = manifest()
    temporary = Path(tempfile.mkdtemp(prefix="c150660-offline-", dir=ROOT / ".runtime-work"))
    for row in rows:
        suffix = row["case_id"][len(FOLDER.name) + 2:]
        for candidate in ("primary", "fallback1"):
            output = temporary / (suffix + "-" + candidate)
            command = [PYTHON, str(ROOT / "runtime.py"), "offline", "--manifest", str(MANIFEST),
                       "--case", row["case_id"], "--output", str(output), "--python", PYTHON]
            if candidate != "primary":
                command += ["--candidate", candidate]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            if completed.returncode:
                print(completed.stdout, completed.stderr, sep="\n")
                if (output / "offline.log").exists():
                    print((output / "offline.log").read_text())
                raise RuntimeError("Offline check failed: " + suffix + " " + candidate)
            log = FOLDER / "native" / (suffix + "-" + candidate + "-offline.log")
            log.write_text((output / "offline.log").read_text().strip() + "\n")
            print(suffix, candidate, digest(log))
