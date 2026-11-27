"""Validate four-case police draft stages in ignored scratch without publication."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c135702-temp/police-semantic"


def proof():
    output = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    runtime_work = (REPO / ".runtime-work").resolve()
    if runtime_work not in output.parents:
        raise ValueError("Runtime output must be under .runtime-work")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from worker_exchange.semantic_delivery import validate

    SCRATCH.mkdir(parents=True, exist_ok=True)
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    manifest = json.loads((ROOT / "police-merge-draft-manifest.json").read_text())
    for entry in manifest["cases"]:
        source = ROOT / entry["construction"]
        target = SCRATCH / entry["construction"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    index = json.loads((ROOT / "proposals/semantic-index.json").read_text())
    for stage, refs in index["stages"].items():
        if stage == "cases":
            continue
        for ref in refs if isinstance(refs, list) else [refs]:
            source = ROOT / ref["path"]
            target = SCRATCH / ref["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    draft = json.loads((ROOT / "proposals/police-cases-draft.json").read_text())
    draft["sweep_specs"] = json.loads((ROOT / "proposals/cases.json").read_text())["sweep_specs"]
    target = SCRATCH / "proposals/cases.json"
    target.write_text(json.dumps(draft, indent=2) + "\n")
    index["stages"]["cases"] = {"path": "proposals/cases.json",
                                 "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    (SCRATCH / "proposals/semantic-index.json").write_text(json.dumps(index, indent=2) + "\n")
    return validate(SCRATCH, assignment, manifest)


if __name__ == "__main__":
    print(json.dumps(proof(), sort_keys=True))
