"""Run exact synthetic comparison pairs and missing-source rejection."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c102642-selected"
ACTIONS = {"open_near_overlap": ("open", "left"),
           "open_near_clear": ("open", "left"),
           "open_far_side": ("open", "right"),
           "board_near": ("board", "left"),
           "alight_near": ("alight", "left")}


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    output = HERE / "comparisons"
    output.mkdir(exist_ok=True)
    scratch = SCRATCH / "comparison-negatives"
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMPDIR=str(REPO / ".runtime-work"), PYTHONDONTWRITEBYTECODE="1")
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        sources = []
        for case_id in comparison["case_ids"]:
            kind = case_id.rsplit("__", 1)[1]
            source = HERE / "cases" / kind / "diagnostic-sources/native-trace.json"
            act, side = ACTIONS[kind]
            sources.append({"case_id": case_id, "path": str(source),
                            "sha256": sha(source), "act": act, "side": side})
        spec = output / (ident + "-source-spec.json")
        write(spec, {"comparison_id": ident, "sources": sources,
                     "diagnostic_fixture": True,
                     "scope": "synthetic comparison logic only; original Native pair pending"})
        report = output / (ident + "-cpu-audit.json")
        command = [sys.executable, str(HERE / "compare_saved.py"),
                   "--plan", str(HERE / "case-plan.json"),
                   "--spec", str(spec), "--expected-comparison-id", ident,
                   "--output", str(report)]
        positive = subprocess.run(command, cwd=REPO, env=env,
                                  capture_output=True, text=True)
        (output / (ident + "-cpu-audit.log")).write_text(positive.stdout + positive.stderr)
        if positive.returncode:
            raise ValueError("comparison failed: " + ident + ": " + positive.stderr[-500:])
        negative_spec = scratch / (ident + "-missing-source.json")
        missing_sources = [dict(item) for item in sources]
        missing_sources[-1]["path"] = str(scratch / (ident + "-absent-trace.json"))
        write(negative_spec, {"comparison_id": ident, "sources": missing_sources})
        negative = subprocess.run([sys.executable, str(HERE / "compare_saved.py"),
                                   "--plan", str(HERE / "case-plan.json"),
                                   "--spec", str(negative_spec),
                                   "--expected-comparison-id", ident,
                                   "--output", str(scratch / (ident + "-negative-output.json"))],
                                  cwd=REPO, env=env, capture_output=True, text=True)
        log = output / (ident + "-missing-source.log")
        log.write_text(negative.stdout + negative.stderr)
        if negative.returncode == 0 or "FileNotFoundError" not in log.read_text():
            raise ValueError("missing source was accepted: " + ident)
        print(ident, "positive=0", "missing_source_rejected", "audit_sha=" + sha(report)[:12])


if __name__ == "__main__":
    prove()
