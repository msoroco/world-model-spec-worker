"""Run pinned exact offline construction checks for diagnostic cases."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove() -> dict:
    manifest_path = HERE / "execution-manifest.diagnostic.json"
    manifest = json.loads(manifest_path.read_text())
    scratch = ROOT / ".runtime-work" / "c229398-offline-diagnostics"
    scratch.mkdir(parents=True, exist_ok=True)
    proofs = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.rsplit("__", 1)[-1]
        output = scratch / kind
        if output.exists():
            shutil.rmtree(output)
        command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"),
                   "offline", "--manifest", str(manifest_path),
                   "--case", case_id, "--output", str(output)]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work" / "c229398-output"),
                   TMPDIR=str(ROOT / ".runtime-work" / "c229398-tmp"))
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        if run.returncode:
            raise ValueError("pinned offline failed: " + kind + "\n" + run.stdout + run.stderr)
        result = json.loads(run.stdout)
        if result.get("offline_passed") is not True or result.get("case_id") != case_id:
            raise ValueError("pinned offline receipt differs: " + kind)
        log_path = HERE / ("cpu-offline-" + kind + ".log")
        content = (output / "offline.log").read_text().strip()
        log_path.write_text((content + "\n" if content else "offline embedded checks passed\n"))
        proofs.append({"case_id": case_id, "construction_sha256": entry["construction_sha256"],
                       "command": " ".join(command), "exit_code": 0,
                       "log": log_path.name, "log_sha256": sha(log_path)})
    result = {"format": "c229398-offline-diagnostic-index-v1",
              "assignment_id": HERE.name, "manifest_sha256": sha(manifest_path),
              "diagnostic_only": True, "case_proofs": proofs,
              "physical_acceptance_claimed": False,
              "legal_acceptance_claimed": False}
    (HERE / "diagnostic-offline-index.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"{len(proofs)} exact pinned offline diagnostic constructions passed")
    return result


if __name__ == "__main__":
    prove()
