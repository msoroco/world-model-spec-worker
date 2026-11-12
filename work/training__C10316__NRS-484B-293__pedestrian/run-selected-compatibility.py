"""Exercise and bind the selected C10316 diagnostic compatibility matrix."""
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


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def run() -> dict:
    if not VALIDATOR.is_file():
        raise ValueError("Pinned Lean decoder validator is absent")
    manifest = json.loads(MANIFEST.read_text())
    if manifest["status"] != "partial_selected_cpu_proofs_pending":
        raise ValueError("Expected selected partial manifest")
    rows = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        for ident in NAMES:
            selected = (entry if ident == "primary" else
                        next(row for row in entry["candidates"]
                             if row["id"] == ident))
            output = ROOT / ".runtime-work" / f"c10316-selected-{suffix}-{ident}-compat"
            receipt_path = output / "compatibility.json"
            command = [str(PYTHON), str(ROOT / "runtime.py"), "compatibility",
                       "--manifest", str(MANIFEST), "--case", case_id,
                       "--candidate", ident, "--output", str(output),
                       "--library", str(LIBRARY), "--validator", str(VALIDATOR)]
            command_log = HERE / f"update016-selected-{suffix}-{ident}-compat.log"
            reuse = receipt_path.is_file() and command_log.is_file()
            if reuse:
                receipt = json.loads(receipt_path.read_text())
                reuse = (receipt.get("passed") is True and
                         receipt.get("case_id") == case_id and
                         receipt.get("candidate_id") == ident and
                         receipt.get("construction_sha256") ==
                         selected["construction_sha256"] and
                         receipt.get("runtime_manifest_sha256") ==
                         manifest["runtime_manifest_sha256"])
            if not reuse:
                if output.exists():
                    raise ValueError("Existing compatibility output differs: " + str(output))
                with command_log.open("w") as stream:
                    completed = subprocess.run(command, cwd=ROOT, stdout=stream,
                                               stderr=subprocess.STDOUT, timeout=600)
                if completed.returncode or not receipt_path.is_file():
                    raise RuntimeError("Selected compatibility failed: " + case_id + " " + ident)
                receipt = json.loads(receipt_path.read_text())
            if (receipt.get("passed") is not True or
                    receipt.get("construction_sha256") != selected["construction_sha256"] or
                    not {"selected_measurements", "negative_case_source",
                         "lean_decoder", "final_decode"} <= set(receipt.get("checks", []))):
                raise ValueError("Incomplete selected compatibility: " + case_id + " " + ident)
            destination = HERE / "update016-selected-proofs" / suffix / ident
            destination.mkdir(parents=True, exist_ok=True)
            for source_name, target_name in (("compatibility.json", "compatibility.json"),
                                             ("compatibility-analysis.log", "analysis.log"),
                                             ("negative-analysis.log", "negative.log")):
                shutil.copyfile(output / source_name, destination / target_name)
            spec = {"receipt": str((destination / "compatibility.json").relative_to(HERE)),
                    "sha256": sha(destination / "compatibility.json"),
                    "log": str((destination / "analysis.log").relative_to(HERE)),
                    "negative_log": str((destination / "negative.log").relative_to(HERE))}
            if (sha(destination / "analysis.log") != receipt["log_sha256"] or
                    sha(destination / "negative.log") != receipt["negative_log_sha256"]):
                raise ValueError("Copied compatibility logs differ")
            selected["compatibility"] = spec
            if ident == "primary":
                entry["negative"] = {"log": spec["negative_log"]}
            rows.append({"case_id": case_id, "candidate_id": ident,
                         "construction_sha256": selected["construction_sha256"],
                         "command": shlex.join(command),
                         "command_log": command_log.name,
                         "command_log_sha256": sha(command_log),
                         "compatibility": spec,
                         "scope": "diagnostic synthetic source; no Native or legal acceptance"})
            print(suffix, ident, "passed", flush=True)
    write(MANIFEST, manifest)
    summary = {"format": "c10316-selected-compatibility-summary-v1",
               "selected_manifest_sha256": sha(MANIFEST),
               "results": rows, "original_native_proven": False}
    write(HERE / "update016-selected-compatibility-summary.json", summary)
    return {"candidate_proofs": len(rows),
            "manifest_sha256": summary["selected_manifest_sha256"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
