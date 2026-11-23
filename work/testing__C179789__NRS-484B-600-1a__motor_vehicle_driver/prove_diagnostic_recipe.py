"""Materialize the reference diagnostic and prove saved joins and video decode."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT_ROOT = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""))
if not OUTPUT_ROOT.is_absolute() or not OUTPUT_ROOT.is_relative_to(ROOT / ".runtime-work"):
    raise SystemExit("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from worker_exchange.media import audit  # noqa: E402
from saved_measurement import analyze, finalize_attempt  # noqa: E402
from tests.test_native_scene import packet  # noqa: E402


def prove():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for case_id, case in packet()["cases"].items():
        suffix = case_id.rsplit("__", 1)[-1]
        folder = HERE if suffix == "reference" else HERE / "diagnostics" / suffix
        output = OUTPUT_ROOT / suffix
        if output.exists():
            raise ValueError("retain previous diagnostic materialization")
        subprocess.run([sys.executable, str(ROOT / "runtime.py"), "fixture", "--recipe",
                        str(folder / "diagnostic-recipe.json"), "--output", str(output)],
                       cwd=ROOT, check=True, stdout=subprocess.PIPE, text=True, timeout=180)
        report = finalize_attempt(output, output / "analysis-report.json")
        if (report["case_id"] != case_id or
                report["measurements"]["basic_speed_observation"]["value"]["legal_judgment"]
                != "unresolved" or
                any(not item["matched"] for item in report["target_checks"])):
            raise ValueError("diagnostic finalizer changed case, target or legal status")
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            decoded = audit(output / (name + ".mkv"), 900)
            if decoded["frames"] != 900:
                raise ValueError("diagnostic four-view frame count differs")
        source = output / "original-conditions.jsonl"
        removed = output / "original-conditions.removed"
        source.rename(removed)
        try:
            try:
                analyze(output)
            except ValueError as error:
                if str(error) != "Missing required source: original-conditions.jsonl":
                    raise
            else:
                raise ValueError("missing original conditions was accepted")
        finally:
            removed.rename(source)
        print(json.dumps({"case_id": case_id, "source_files": 8, "decoded_views": 4,
                          "decoded_frames_per_view": 900, "negative_missing_source": "rejected",
                          "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    prove()
