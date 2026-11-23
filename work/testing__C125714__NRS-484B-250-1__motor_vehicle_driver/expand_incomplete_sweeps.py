"""Run the pinned expander while retaining both unresolved source guards."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main() -> None:
    proposal = ROOT / "proposals/cases.json"
    before = json.loads(proposal.read_text())
    if (len(before["cases"]) != 8 or len(before["sweep_specs"]) != 2 or
            any(spec.get("status") != "incomplete" for spec in before["sweep_specs"])):
        raise ValueError("source-bound judgment gaps changed")
    private = REPO / ".runtime-work/c125714-sweep-expansion"
    private.mkdir(parents=True, exist_ok=True)
    templates = private / "templates.json"
    templates.write_text(json.dumps([json.loads((ROOT / "proposals/template.json").read_text())]) + "\n")
    output = private / "expanded-cases.json"
    if output.exists():
        output.unlink()
    command = [sys.executable, str(REPO / "runtime.py"), "expand", "--proposal", str(proposal),
               "--templates", str(templates), "--bindings", str(ROOT / "proposals/bindings.json"),
               "--output", str(output)]
    subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                   check=True, timeout=60)
    value = json.loads(output.read_text())
    if (value.get("sweeps_expanded") is not True or len(value["cases"]) != 8 or
            value["sweep_specs"] != before["sweep_specs"]):
        raise ValueError("pinned expansion changed source gaps or exact case count")
    proposal.write_text(json.dumps(value, indent=2) + "\n")
    index_path = ROOT / "proposals/semantic-index.json"
    index = json.loads(index_path.read_text())
    index["stages"]["cases"]["sha256"] = hashlib.sha256(proposal.read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    print("two incomplete source-bound sweeps passed pinned expansion without source invention")


if __name__ == "__main__":
    main()
