"""Run and bind exact selected C10316 offline proofs for all candidates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
PYTHON = ROOT / ".venv-cpu/bin/python"
NAMES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def run() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    if manifest["status"] != "partial_selected_cpu_proofs_pending":
        raise ValueError("Expected selected partial manifest")
    run_root = Path(tempfile.mkdtemp(dir=ROOT / ".runtime-work",
                                     prefix="c10316-selected-offline-"))
    results = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        for ident in NAMES:
            selected = (entry if ident == "primary" else
                        next(row for row in entry["candidates"]
                             if row["id"] == ident))
            if sha(HERE / selected["construction"]) != selected["construction_sha256"]:
                raise ValueError("Selected construction changed: " + case_id + " " + ident)
            output = run_root / (suffix + "-" + ident)
            command = [str(PYTHON), str(ROOT / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", case_id,
                       "--candidate", ident, "--output", str(output),
                       "--python", str(PYTHON)]
            completed = subprocess.run(command, cwd=ROOT, text=True,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, timeout=300)
            log = HERE / f"update016-selected-{suffix}-{ident}-offline.log"
            log.write_text(completed.stdout)
            row = {"case_id": case_id, "candidate_id": ident,
                   "construction_sha256": selected["construction_sha256"],
                   "command": shlex.join(command),
                   "exit_code": completed.returncode,
                   "log": log.name, "log_sha256": sha(log),
                   "scope": "selected CPU offline only; no Native realization"}
            if completed.returncode != 0 or not (output / "offline.log").is_file():
                raise RuntimeError("Selected offline failed: " + case_id + " " + ident)
            unit = HERE / f"update016-selected-{suffix}-{ident}-unit.log"
            unit.write_bytes((output / "offline.log").read_bytes())
            row.update(unit_log=unit.name, unit_log_sha256=sha(unit))
            selected["offline"] = {key: row[key] for key in
                                   ("construction_sha256", "command", "exit_code",
                                    "log", "log_sha256")}
            results.append(row)
    write(MANIFEST, manifest)
    summary = {"format": "c10316-selected-offline-summary-v1",
               "selected_manifest_sha256": sha(MANIFEST),
               "results": results, "original_native_proven": False}
    write(HERE / "update016-selected-offline-summary.json", summary)
    return {"cases": len(manifest["cases"]), "candidate_proofs": len(results),
            "manifest_sha256": summary["selected_manifest_sha256"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
