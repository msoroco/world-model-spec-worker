"""Rerun current-manifest compatibility and recorded-only processing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
PYTHON = ROOT / ".venv-cpu/bin/python"
LIBRARY = ROOT / "runtime/pipeline/library"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"
NAMES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def verify(case_id: str, ident: str, expected_sha: str,
           attempt: Path, saved: Path, manifest_sha: str) -> dict:
    selection = read(attempt / "candidate-selection.json")
    compat = read(attempt / "compatibility.json")
    processing = read(saved / "v0001/processing.json")
    if (selection.get("case_id") != case_id or
            selection.get("candidate_id") != ident or
            selection.get("construction_sha256") != expected_sha or
            selection.get("manifest_sha256") != manifest_sha or
            compat.get("passed") is not True or
            compat.get("case_id") != case_id or
            compat.get("candidate_id") != ident or
            compat.get("construction_sha256") != expected_sha or
            processing.get("passed") is not True or
            processing.get("case_id") != case_id or
            processing.get("candidate_id") != ident or
            processing.get("native_revision", {}).get("construction_sha256") != expected_sha or
            processing.get("originals_preserved") is not True or
            processing.get("missing_evidence") is not False):
        raise ValueError("Current-manifest saved proof differs: " + case_id + " " + ident)
    return processing


def run() -> dict:
    manifest_sha = sha(MANIFEST)
    manifest = read(MANIFEST)
    rows = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        for ident in NAMES:
            selected = (entry if ident == "primary" else
                        next(item for item in entry["candidates"]
                             if item["id"] == ident))
            attempt = ROOT / ".runtime-work" / f"c10316-current-{suffix}-{ident}-compat"
            saved = ROOT / ".runtime-work" / f"c10316-current-{suffix}-{ident}-saved"
            compat_log = HERE / f"update017-current-{suffix}-{ident}-compat.log"
            saved_log = HERE / f"update017-current-{suffix}-{ident}-saved.log"
            compat_command = [str(PYTHON), str(ROOT / "runtime.py"), "compatibility",
                              "--manifest", str(MANIFEST), "--case", case_id,
                              "--candidate", ident, "--output", str(attempt),
                              "--library", str(LIBRARY), "--validator", str(VALIDATOR)]
            saved_command = [str(PYTHON), str(ROOT / "runtime.py"), "process-saved",
                             "--manifest", str(MANIFEST), "--case", case_id,
                             "--attempt", str(attempt), "--output", str(saved),
                             "--library", str(LIBRARY), "--validator", str(VALIDATOR)]
            if not (attempt / "compatibility.json").is_file():
                if attempt.exists():
                    raise ValueError("Partial compatibility output exists: " + str(attempt))
                with compat_log.open("w") as stream:
                    result = subprocess.run(compat_command, cwd=ROOT, stdout=stream,
                                            stderr=subprocess.STDOUT, timeout=600)
                if result.returncode:
                    raise RuntimeError("Current compatibility failed: " + case_id + " " + ident)
            if not compat_log.is_file():
                raise ValueError("Missing current compatibility log")
            selection = read(attempt / "candidate-selection.json")
            if selection.get("manifest_sha256") != manifest_sha:
                raise ValueError("Compatibility attempt binds another manifest")
            if not (saved / "v0001/processing.json").is_file():
                if saved.exists():
                    raise ValueError("Partial saved output exists: " + str(saved))
                with saved_log.open("w") as stream:
                    result = subprocess.run(saved_command, cwd=ROOT, stdout=stream,
                                            stderr=subprocess.STDOUT, timeout=600)
                if result.returncode:
                    raise RuntimeError("Current saved processing failed: " + case_id + " " + ident)
            if not saved_log.is_file():
                raise ValueError("Missing current saved-processing log")
            verify(case_id, ident, selected["construction_sha256"],
                   attempt, saved, manifest_sha)
            target = HERE / "update017-current-proofs" / suffix / ident
            target.mkdir(parents=True, exist_ok=True)
            for source, name in ((attempt / "candidate-selection.json", "candidate-selection.json"),
                                 (attempt / "compatibility.json", "compatibility.json"),
                                 (attempt / "compatibility-analysis.log", "analysis.log"),
                                 (attempt / "negative-analysis.log", "negative.log"),
                                 (saved / "v0001/processing.json", "processing.json")):
                shutil.copyfile(source, target / name)
            rows.append({"case_id": case_id, "candidate_id": ident,
                         "construction_sha256": selected["construction_sha256"],
                         "compatibility_command": shlex.join(compat_command),
                         "saved_command": shlex.join(saved_command),
                         "compatibility_log": compat_log.name,
                         "compatibility_log_sha256": sha(compat_log),
                         "saved_log": saved_log.name,
                         "saved_log_sha256": sha(saved_log),
                         "proofs": {name: sha(target / name) for name in
                                    ("candidate-selection.json", "compatibility.json",
                                     "analysis.log", "negative.log", "processing.json")},
                         "scope": "synthetic recorded-only diagnostic; no physical or legal acceptance"})
            print(suffix, ident, "current saved passed", flush=True)
    if sha(MANIFEST) != manifest_sha:
        raise ValueError("Manifest changed during current saved proof run")
    summary = {"format": "c10316-current-selected-saved-summary-v1",
               "manifest_sha256": manifest_sha, "results": rows,
               "original_native_proven": False,
               "physical_or_legal_acceptance": False}
    target = HERE / "update017-current-saved-summary.json"
    target.write_text(json.dumps(summary, indent=2) + "\n")
    return {"saved_proofs": len(rows), "manifest_sha256": manifest_sha,
            "summary_sha256": sha(target)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
