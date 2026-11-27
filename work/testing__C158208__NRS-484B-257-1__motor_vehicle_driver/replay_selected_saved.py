"""Replay selected-manifest saved-only analysis on synthetic CPU source stages."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(compat_root: Path, scratch_root: Path, validator: Path) -> dict:
    work_root = ROOT / "work"
    private = ROOT / ".runtime-work"
    scratch_root = scratch_root.resolve()
    if private not in scratch_root.parents or scratch_root.exists() or work_root in scratch_root.parents:
        raise ValueError("new private scratch directory under .runtime-work required")
    if not validator.is_file():
        raise ValueError("pinned built Lean decoder required")
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest_sha = sha(manifest_path)
    rows = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.rsplit("__", 1)[-1]
        for candidate_id, selected in (("primary", entry),
                                       ("fallback1", entry["candidates"][0])):
            attempt = scratch_root / "attempts" / kind / candidate_id
            attempt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(compat_root / kind / candidate_id, attempt)
            selection_path = attempt / "candidate-selection.json"
            selection = json.loads(selection_path.read_text())
            if (selection.get("case_id") != case_id or
                    selection.get("candidate_id") != candidate_id or
                    selection.get("construction_sha256") != selected["construction_sha256"]):
                raise ValueError("synthetic source attempt identity differs")
            selection["manifest_sha256"] = manifest_sha
            selection_path.write_text(json.dumps(selection, indent=2) + "\n")
            output = scratch_root / "derived" / kind / candidate_id
            command = [sys.executable, str(ROOT / "runtime.py"), "process-saved",
                       "--manifest", str(manifest_path), "--case", case_id,
                       "--attempt", str(attempt), "--output", str(output),
                       "--library", str(ROOT / "runtime/library"),
                       "--validator", str(validator)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            folder = HERE / "cases" / kind / candidate_id
            log = folder / "selected-saved.log"
            log.write_text((result.stdout + result.stderr).rstrip() + "\n")
            if result.returncode:
                raise ValueError("selected saved-only replay failed: " + kind + "/" + candidate_id)
            receipt = json.loads(result.stdout)
            if (receipt.get("case_id") != case_id or
                    receipt.get("candidate_id") != candidate_id or
                    receipt.get("passed") is not True or
                    receipt.get("recorded_only") is not True or
                    receipt.get("native_revision", {}).get("construction_sha256") !=
                    selected["construction_sha256"]):
                raise ValueError("selected saved-only receipt differs")
            returned = folder / "selected-saved-receipt.json"
            returned.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            rows.append({"case_id": case_id, "candidate_id": candidate_id,
                         "construction_sha256": selected["construction_sha256"],
                         "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                         "receipt": str(returned.relative_to(HERE)),
                         "receipt_sha256": sha(returned), "exit_code": 0})
    index = {"format": "c158208-selected-saved-cpu-index-v1",
             "assignment_id": HERE.name, "manifest_sha256": manifest_sha,
             "scope": "synthetic_fixture_saved_only",
             "physical_acceptance_claimed": False,
             "legal_acceptance_claimed": False, "cases": rows}
    path = HERE / "selected-saved-index.json"
    path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    return {"replayed_candidates": len(rows), "index_sha256": sha(path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compat-root", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--validator", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.compat_root, args.scratch_root, args.validator), indent=2))
