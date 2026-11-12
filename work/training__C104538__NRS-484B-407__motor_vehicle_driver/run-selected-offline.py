"""Run exact selected construction checks for the 500-foot sweep."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
PYTHON = ROOT / ".venv-cpu/bin/python"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    manifest_sha = sha(MANIFEST)
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            selected = (entry if candidate == "primary" else
                        next(item for item in entry["candidates"]
                             if item["id"] == candidate))
            output = ROOT / ".runtime-work" / f"c104538-selected-offline-{suffix}-{candidate}"
            log = HERE / f"update016-selected-{suffix}-{candidate}-offline.log"
            command = [str(PYTHON), str(ROOT / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", case,
                       "--candidate", candidate, "--output", str(output),
                       "--python", str(PYTHON)]
            if not log.is_file():
                if output.exists():
                    raise ValueError("Partial offline output exists: " + str(output))
                with log.open("w") as stream:
                    result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                            stderr=subprocess.STDOUT, timeout=300)
                if result.returncode:
                    raise RuntimeError("Selected offline failed: " + case + " " + candidate)
            receipt = json.loads(log.read_text())
            if (receipt.get("offline_passed") is not True or
                    receipt.get("simulation_started") is not False or
                    receipt.get("case_id") != case or
                    receipt.get("candidate_id") != candidate):
                raise ValueError("Selected offline receipt incomplete")
            rows.append({"case_id": case, "candidate_id": candidate,
                         "construction_sha256": selected["construction_sha256"],
                         "command": shlex.join(command), "log": log.name,
                         "log_sha256": sha(log), "offline_passed": True,
                         "simulation_started": False})
            print(suffix, candidate, "offline passed", flush=True)
    if sha(MANIFEST) != manifest_sha:
        raise ValueError("Selected manifest changed during offline matrix")
    summary = {"format": "c104538-selected-offline-summary-v1",
               "manifest_sha256": manifest_sha, "results": rows,
               "simulation_started": False}
    path = HERE / "update016-selected-offline-summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    return {"offline_proofs": len(rows), "summary_sha256": sha(path)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
