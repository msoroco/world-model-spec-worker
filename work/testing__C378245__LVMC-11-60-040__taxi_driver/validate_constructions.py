"""Check six exact taxi bundles with the pinned construction stage validator."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output_root or (REPO / ".runtime-work").resolve() not in Path(output_root).resolve().parents:
    raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from batch_pipeline import stages  # noqa: E402


def check() -> None:
    original = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    proposal = json.loads((ROOT / "proposals/cases.json").read_text())
    manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    selected = {c["case_id"]: c for c in proposal["cases"] if c["target_type"] != "baseline"}
    if set(selected) != {entry["case_id"] for entry in manifest["cases"]}:
        raise ValueError("semantic and construction case coverage differs")
    for entry in manifest["cases"]:
        path = ROOT / entry["construction"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["construction_sha256"]:
            raise ValueError("exact construction source hash changed")
        construction = json.loads(path.read_text())
        case = selected[entry["case_id"]]
        stages.validate("construction", construction,
                        {"request": {"cell": original["cell"], "actor": original["actor"],
                                     "case": case}, "dependencies": []})
        for file in construction["files"]:
            if file.get("source") and (REPO / file["source"]).read_text() != file["content"]:
                raise ValueError("inline exact construction source changed")
        proof = entry["offline"]
        if proof["exit_code"] != 0 or proof["construction_sha256"] != entry["construction_sha256"]:
            raise ValueError("exact offline proof not bound")
        if hashlib.sha256((ROOT / proof["log"]).read_bytes()).hexdigest() != proof["log_sha256"]:
            raise ValueError("exact offline log changed")
        print(entry["case_id"].split("__")[-1], "construction and offline proof PASS")


if __name__ == "__main__":
    check()
