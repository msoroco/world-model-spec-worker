"""Reproduce offline and saved positive/negative CPU proofs for three exact IDs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VARIANTS = ("precedence", "advance", "other_later")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_command(command, log, env=None):
    with Path(log).open("w") as stream:
        completed = subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, timeout=300)
    return completed.returncode


def merge_sources(source, target):
    for item in source.rglob("*"):
        if item.is_file():
            destination = target / item.relative_to(source)
            if destination.exists():
                raise ValueError("fixture shadows construction: " + destination.name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, destination)


def prove(base):
    base = Path(base).resolve()
    if REPO / ".runtime-work" not in base.parents or base.exists():
        raise ValueError("use a fresh proof directory under .runtime-work")
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not output_root or (REPO / ".runtime-work") not in Path(output_root).resolve().parents:
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    base.mkdir(parents=True)
    for suffix in VARIANTS:
        folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
        case_id = ROOT.name + "__" + suffix
        attempt = base / suffix
        offline = attempt / "offline"
        fixture = attempt / "fixture"
        attempt.mkdir()
        command = [sys.executable, str(REPO / "runtime.py"), "offline",
                   "--manifest", str(ROOT / "diagnostic-execution-manifest.json"),
                   "--case", case_id, "--output", str(offline),
                   "--python", sys.executable]
        if run_command(command, attempt / "offline-command.log") != 0:
            raise ValueError("offline diagnostic failed: " + suffix)
        recipe = folder / "diagnostic-recipe.json"
        command = [sys.executable, str(REPO / "runtime.py"), "fixture",
                   "--recipe", str(recipe), "--output", str(fixture)]
        if run_command(command, attempt / "fixture-command.log") != 0:
            raise ValueError("fixture generation failed: " + suffix)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join((str(REPO / "runtime/scenario_pipeline"),
                                              str(REPO / "runtime/python")))
        for label in ("positive", "negative"):
            target = attempt / label
            shutil.copytree(offline, target)
            merge_sources(fixture, target)
            if label == "negative":
                (target / "other-body-history.jsonl").unlink()
            command = [sys.executable, str(target / "analysis.py"), "--attempt", str(target),
                       "--output", str(target / "analysis-report.json")]
            exit_code = run_command(command, attempt / (label + ".log"), env)
            if (exit_code == 0) != (label == "positive"):
                raise ValueError("unexpected saved finalizer status: " + suffix + "/" + label)
        positive = attempt / "positive"
        for source in fixture.rglob("*"):
            if source.is_file() and sha(source) != sha(positive / source.relative_to(fixture)):
                raise ValueError("saved finalizer changed acquired source")
        result = json.loads((positive / "result.json").read_text())
        report = json.loads((positive / "analysis-report.json").read_text())
        observed = report["measurements"]["crossing_entry_measurement"]["value"]
        expected_other_first = suffix != "other_later"
        if (result["case_id"] != case_id or
                observed["other_entered_before_ego"] is not expected_other_first or
                result["physical_checks"]["maneuver"]["status"] != "met" or
                result["measured_values"]["legal_judgment"] != "unresolved" or
                result["physical_acceptance_claimed"] is not False):
            raise ValueError("diagnostic saved measurement differs: " + suffix)
        missing = "Missing required original Native source: other-body-history.jsonl"
        if missing not in (attempt / "negative.log").read_text():
            raise ValueError("negative case did not reject missing original source")
        for source, name in ((offline / "offline.log", "diagnostic-offline.log"),
                             (positive / "result.json", "diagnostic-saved-result.json"),
                             (positive / "analysis-report.json", "diagnostic-analysis-report.json"),
                             (attempt / "negative.log", "diagnostic-negative.log")):
            shutil.copyfile(source, folder / name)
        proof = {"format": "c125714-diagnostic-saved-proof", "diagnostic_only": True,
                 "case_id": case_id, "construction_sha256": sha(folder / "construction.json"),
                 "fixture_recipe_sha256": sha(recipe), "fixture_source_sha256": sha(folder / "diagnostic.json"),
                 "positive_result": "diagnostic-saved-result.json",
                 "positive_result_sha256": sha(folder / "diagnostic-saved-result.json"),
                 "positive_report": "diagnostic-analysis-report.json",
                 "positive_report_sha256": sha(folder / "diagnostic-analysis-report.json"),
                 "negative_log": "diagnostic-negative.log",
                 "negative_log_sha256": sha(folder / "diagnostic-negative.log"),
                 "negative_missing_source": "other-body-history.jsonl",
                 "acquisition_unchanged": True, "physical_fixture_status": "met",
                 "other_entered_before_ego": expected_other_first,
                 "legal_judgment": "unresolved", "physical_acceptance_claimed": False,
                 "compatibility_claimed": False}
        (folder / "diagnostic-saved-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
        (folder / "diagnostic-saved-proof.log").write_text(
            f"{case_id}: offline and positive saved finalization passed; synthetic entry order {expected_other_first}; "
            "negative missing other-body history rejected; legal judgment unresolved; no physical acceptance or full compatibility claim.\n")
        print(json.dumps({"case_id": case_id, "offline": "passed", "saved_positive": "passed",
                          "saved_negative": "rejected", "diagnostic_only": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    prove(parser.parse_args().output_root)
