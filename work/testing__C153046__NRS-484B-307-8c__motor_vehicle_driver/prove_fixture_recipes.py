"""Validate all inventories and one full decoded four-view diagnostic source."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
sys.path.insert(0, str(ASSIGNMENT))

from scenario_pipeline.worker_exchange.fixture_recipe import inspect, materialize
from scenario_pipeline.worker_exchange.media import check_four_view_sources
from scenario_pipeline.worker_exchange.measurement_contract import verify_report
from build_case_plan import KINDS
from saved_measurement import finalize_attempt


def main() -> None:
    for suffix in KINDS:
        path = ASSIGNMENT / "diagnostics" / suffix / "fixture-recipe.json"
        recipe, sources = inspect(ROOT, path)
        if len(sources) != 1 or recipe["generator"]["source"].split("/")[-1] != "diagnostic.json":
            raise ValueError("diagnostic source inventory differs: " + suffix)
        print("pinned source recipe inspected", suffix)
    suffix = "stopped_leftmost_clear"
    private = ROOT / ".runtime-work" / "c153046-fixture-proof"
    private.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=private) as temporary:
        fixture = Path(temporary) / "positive"
        recipe = ASSIGNMENT / "diagnostics" / suffix / "fixture-recipe.json"
        source = materialize(ROOT, recipe, fixture)
        required = {"site.json", "trace.jsonl", "video_frames.jsonl", "road.xodr",
                    "capture/evidence.jsonl", "capture/native/frames.jsonl",
                    "capture/manifest.json", *(name + ".mkv" for name in
                    ("overview", "approach", "reference_corner", "driver_reference"))}
        if not required <= set(source["fixture_manifest"]) or len(source["fixture_manifest"]) < 30:
            raise ValueError("diagnostic source inventory lacks text or cameras")
        videos = {name: fixture / (name + ".mkv") for name in
                  ("overview", "approach", "reference_corner", "driver_reference")}
        check_four_view_sources(videos)
        construction = json.loads((ASSIGNMENT / "constructions" / (suffix + ".json")).read_text())
        config = next(item["content"] for item in construction["files"] if item["path"] == "config.json")
        (fixture / "config.json").write_text(config)
        report = finalize_attempt(fixture, fixture / "analysis-report.json")
        contract = json.loads((ASSIGNMENT / "constructions" /
                               (suffix + "-measurement-contract.json")).read_text())
        verify_report(contract, report, fixture)
        print("full decoded four-view diagnostic and saved measurement passed", suffix)


if __name__ == "__main__":
    main()
