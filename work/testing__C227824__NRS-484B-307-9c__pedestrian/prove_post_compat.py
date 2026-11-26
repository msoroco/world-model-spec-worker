"""Reprove saved-only, physical and independent audit paths for one exact case."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from ped_entry import CASES
from delivery_audit import ASSIGNMENT


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c227824-owner"
PYTHON = str(REPO / ".venv-cpu/bin/python")
VALIDATOR = SCRATCH / "decoder/.lake/build/bin/adapterCheck"


def run(args: list[str], expected: int, log: Path) -> None:
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               TMPDIR=str(SCRATCH), MPLCONFIGDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(REPO / "runtime") + os.pathsep + str(REPO / "runtime/scenario_pipeline"))
    result = subprocess.run(args, cwd=REPO, env=env, capture_output=True, text=True)
    content = (result.stdout + result.stderr).rstrip() + "\n"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(content, encoding="utf-8")
    if result.returncode != expected:
        raise ValueError(f"proof returned {result.returncode}, expected {expected}: {log}\n{content[-1500:]}")


def prove(suffix: str) -> None:
    if suffix not in {case.case_id for case in CASES}:
        raise ValueError("exact selected case required")
    cid = ASSIGNMENT + "__" + suffix
    compat = SCRATCH / ("compat5-" + suffix)
    if not json.loads((compat / "compatibility.json").read_text()).get("passed"):
        raise ValueError("current compatibility proof missing")
    saved = SCRATCH / ("saved5-" + suffix)
    saved_log = SCRATCH / ("saved5-" + suffix + ".log")
    if not saved_log.is_file() or not json.loads(saved_log.read_text()).get("passed"):
        run([PYTHON, str(REPO / "runtime.py"), "process-saved", "--manifest",
             f"work/{ASSIGNMENT}/diagnostic-execution-manifest.json", "--case", cid,
             "--attempt", str(compat), "--output", str(saved), "--library", "runtime/library",
             "--validator", str(VALIDATOR)], 0, saved_log)
    folder = ROOT / "cases" / suffix
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        target = folder / ("physical-" + kind)
        scratch_result = SCRATCH / ("post5-" + suffix + "-physical-" + kind + ".json")
        scratch_result.unlink(missing_ok=True)
        run([PYTHON, str(ROOT / "prove_physical.py"), "--case", cid,
             "--kind", kind, "--attempt", str(compat), "--output", str(scratch_result)],
            0, target.with_suffix(".log"))
        target.with_suffix(".json").write_bytes(scratch_result.read_bytes())
    run([PYTHON, str(ROOT / "prove_lifecycle.py"), "--case", cid,
         "--attempt", str(compat), "--saved-receipt", str(saved_log)],
        0, folder / "physical-lifecycle.log")
    run([PYTHON, str(ROOT / "prove_delivery_contract.py"), "--case", cid,
         "--mode", "diagnostic-positive"], 0, folder / "delivery-diagnostic-positive.log")
    run([PYTHON, str(ROOT / "prove_delivery_contract.py"), "--case", cid,
         "--mode", "delivery-negative"], 1, folder / "delivery-delivery-negative.log")
    if "released original" not in (folder / "delivery-delivery-negative.log").read_text():
        raise ValueError("delivery negative did not reject the unreleased source")
    print(json.dumps({"case_id": cid, "saved_only": True, "physical_fixtures": 3,
                      "delivery_positive": True, "delivery_negative": True}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--suffix", required=True)
    prove(parser.parse_args().suffix)
