"""Run the pinned sweep expander while retaining the incomplete judgment status."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = ROOT / "proposals/cases.json"
    value = json.loads(source.read_text())
    specs = value.get("sweep_specs", [])
    if len(specs) != 1 or specs[0].get("status") != "incomplete":
        raise ValueError("the unresolved school-source judgment must be retained")
    private = REPO / ".runtime-work/c255863-sweep-expansion"
    private.mkdir(parents=True, exist_ok=True)
    templates = private / "templates.json"
    templates.write_text(json.dumps([json.loads((ROOT / "proposals/template.json").read_text())]) + "\n")
    output = private / "expanded-cases.json"
    if output.exists():
        output.unlink()
    command = [sys.executable, str(REPO / "runtime.py"), "expand",
               "--proposal", str(source), "--templates", str(templates),
               "--bindings", str(ROOT / "proposals/bindings.json"),
               "--output", str(output)]
    subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                   check=True, timeout=120)
    expanded = json.loads(output.read_text())
    if (expanded.get("sweeps_expanded") is not True or
            expanded["sweep_specs"][0]["status"] != "incomplete" or
            len(expanded["cases"]) != len(value["cases"])):
        raise ValueError("pinned expansion changed the unresolved sweep or case count")
    source.write_text(json.dumps(expanded, indent=2) + "\n")
    index_path = ROOT / "proposals/semantic-index.json"
    index = json.loads(index_path.read_text())
    index["stages"]["cases"]["sha256"] = sha(source)
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    print("pinned sweep expansion retained incomplete source-bound school-source judgment")


if __name__ == "__main__":
    main()
