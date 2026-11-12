"""Prove selected compatibility and recorded-only saved processing for all candidates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import argparse


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


def run(*, primaries_only: bool = False) -> dict:
    if not VALIDATOR.is_file():
        raise ValueError("Pinned Lean decoder validator is absent")
    manifest_sha = sha(MANIFEST)
    manifest = read(MANIFEST)
    if manifest.get("status") != "partial_selected_cpu_proofs_pending":
        raise ValueError("Expected selected partial manifest")
    rows = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        for ident in (("primary",) if primaries_only else NAMES):
            selected = (entry if ident == "primary" else
                        next(row for row in entry["candidates"] if row["id"] == ident))
            name = ("c104538-selected-below-primary" if
                    suffix == "below_500_ft" and ident == "primary" else
                    f"c104538-selected-{suffix}-{ident}")
            attempt = ROOT / ".runtime-work" / (name + "-compat")
            saved = ROOT / ".runtime-work" / (name + "-saved")
            log_name = ("below-primary" if
                        suffix == "below_500_ft" and ident == "primary" else
                        f"{suffix}-{ident}")
            compat_log = HERE / f"update016-selected-{log_name}-compat.log"
            saved_log = HERE / f"update016-selected-{log_name}-saved.log"
            compat_command = [str(PYTHON), str(ROOT / "runtime.py"), "compatibility",
                              "--manifest", str(MANIFEST), "--case", case_id,
                              "--candidate", ident, "--output", str(attempt),
                              "--library", str(LIBRARY), "--validator", str(VALIDATOR)]
            if ident != "primary":
                compat_command = [str(PYTHON), str(HERE / "candidate_compatibility.py"),
                                  "--manifest", str(MANIFEST), "--case", case_id,
                                  "--candidate", ident,
                                  "--recipe", str(HERE / f"update015-{suffix}-{ident}-recipe.json"),
                                  "--output", str(attempt), "--library", str(LIBRARY),
                                  "--validator", str(VALIDATOR)]
            saved_command = [str(PYTHON), str(ROOT / "runtime.py"), "process-saved",
                             "--manifest", str(MANIFEST), "--case", case_id,
                             "--attempt", str(attempt), "--output", str(saved),
                             "--library", str(LIBRARY), "--validator", str(VALIDATOR)]
            if not (attempt / "compatibility.json").is_file():
                if attempt.exists():
                    raise ValueError("Partial compatibility output exists: " + str(attempt))
                with compat_log.open("w") as stream:
                    outcome = subprocess.run(compat_command, cwd=ROOT, stdout=stream,
                                             stderr=subprocess.STDOUT, timeout=600)
                if outcome.returncode:
                    raise RuntimeError("Selected compatibility failed: " + case_id + " " + ident)
            if not (saved / "v0001/processing.json").is_file():
                if saved.exists():
                    raise ValueError("Partial saved output exists: " + str(saved))
                with saved_log.open("w") as stream:
                    outcome = subprocess.run(saved_command, cwd=ROOT, stdout=stream,
                                             stderr=subprocess.STDOUT, timeout=600)
                if outcome.returncode:
                    raise RuntimeError("Selected saved processing failed: " + case_id + " " + ident)
            selection = read(attempt / "candidate-selection.json")
            compat = read(attempt / "compatibility.json")
            processing = read(saved / "v0001/processing.json")
            if (selection.get("manifest_sha256") != manifest_sha or
                    selection.get("construction_sha256") != selected["construction_sha256"] or
                    selection.get("case_id") != case_id or
                    selection.get("candidate_id") != ident or
                    compat.get("passed") is not True or
                    compat.get("construction_sha256") != selected["construction_sha256"] or
                    processing.get("passed") is not True or
                    processing.get("originals_preserved") is not True or
                    processing.get("missing_evidence") is not False or
                    processing.get("case_id") != case_id or
                    processing.get("candidate_id") != ident or
                    processing.get("native_revision", {}).get("construction_sha256") !=
                        selected["construction_sha256"]):
                raise ValueError("Selected current proof binding differs: " + case_id + " " + ident)
            target = HERE / "update016-selected-proofs" / suffix / ident
            target.mkdir(parents=True, exist_ok=True)
            for source, destination in (
                    (attempt / "candidate-selection.json", "candidate-selection.json"),
                    (attempt / "compatibility.json", "compatibility.json"),
                    (attempt / "compatibility-analysis.log", "analysis.log"),
                    (attempt / "negative-analysis.log", "negative.log"),
                    (saved / "v0001/processing.json", "processing.json")):
                shutil.copyfile(source, target / destination)
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
                         "synthetic_diagnostic": True,
                         "original_native_proven": False})
            print(suffix, ident, "current selected saved passed", flush=True)
    if sha(MANIFEST) != manifest_sha:
        raise ValueError("Manifest changed during proof run")
    summary = {"format": "c104538-selected-current-cpu-summary-v1",
               "manifest_sha256": manifest_sha, "results": rows,
               "primaries_only": primaries_only,
               "original_native_proven": False,
               "physical_or_legal_acceptance": False}
    path = HERE / ("update016-selected-primary-summary.json" if primaries_only
                   else "update016-selected-current-summary.json")
    path.write_text(json.dumps(summary, indent=2) + "\n")
    return {"candidate_proofs": len(rows), "manifest_sha256": manifest_sha,
            "summary_sha256": sha(path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--primaries-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(primaries_only=args.primaries_only), indent=2))
