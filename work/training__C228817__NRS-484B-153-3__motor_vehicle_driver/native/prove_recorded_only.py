"""Run selected saved processing on synthetic original sources and a missing source."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from worker_exchange.fixture_recipe import materialize as fixture_materialize
from worker_exchange.runtime_cli import materialize
from worker_exchange.saved_processing import copy_sources


ROOT = Path(__file__).resolve().parent
FOLDER = ROOT.parent
REPO = FOLDER.parents[1]


def run(number):
    base = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "recorded-only" / ("probe-" + str(number))
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    case = FOLDER.name + "__probe_" + str(number)
    manifest = FOLDER / "execution-manifest.json"
    attempt, sources = base / "positive", base / "fixture"
    materialize(manifest, case, attempt)
    fixture_materialize(REPO, ROOT / ("probe-" + str(number) + "-fixture-recipe.json"), sources)
    copy_sources(sources, attempt)
    missing = base / "missing"
    shutil.copytree(attempt, missing, copy_function=os.link)
    (missing / "original-scene-review.json").unlink()
    validator = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "decoder/.lake/build/bin/adapterCheck"
    results = {}
    for label, selected in (("positive", attempt), ("missing", missing)):
        output = base / ("output-" + label)
        cmd = [sys.executable, "-B", str(REPO / "runtime.py"), "process-saved",
               "--manifest", str(manifest), "--case", case,
               "--attempt", str(selected), "--output", str(output),
               "--library", str(REPO / "runtime/library"),
               "--validator", str(validator)]
        completed = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                                   timeout=1200)
        (base / (label + ".log")).write_text(
            (completed.stdout + completed.stderr).rstrip() + "\n")
        if completed.returncode:
            raise ValueError(label + " saved processing failed: " + completed.stderr[-2000:])
        receipt = json.loads((output / "v0001/processing.json").read_text())
        if not (receipt["passed"] and receipt["recorded_only"] and
                receipt["originals_preserved"] and receipt["final_video_checks"]):
            raise ValueError("Incomplete recorded-only proof: " + label)
        if receipt["missing_evidence"] != (label == "missing"):
            raise ValueError("Wrong missing-evidence classification")
        if label == "missing":
            feedback = json.loads((output / "v0001/feedback.json").read_text())
            if feedback["classification"] != "incomplete_or_unavailable_law_evidence" or \
                    feedback["native_replay_requested"] is not False:
                raise ValueError("Missing original did not produce saved-only feedback")
        results[label] = {"recorded_only": True,
                          "originals_preserved": True,
                          "missing_evidence": receipt["missing_evidence"],
                          "full_final_decode": True, "exit_code": completed.returncode}
    return {"format": "c228817-recorded-only-diagnostic-proof-v1",
            "case_id": case, "synthetic_diagnostic": True,
            "positive": results["positive"], "missing": results["missing"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=int, choices=(1, 2, 3, 4), required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.probe), sort_keys=True))
