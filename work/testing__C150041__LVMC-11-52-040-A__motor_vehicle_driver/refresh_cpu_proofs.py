"""Refresh current six-case synthetic fixture and offline proof log bindings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / ".venv-cpu/bin/python"
PREFIX = ROOT.relative_to(REPO).as_posix()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, log):
    result = subprocess.run([str(value) for value in args], cwd=REPO,
                            capture_output=True, text=True, timeout=300)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(str(log) + " failed: " + result.stderr[-800:])
    return {"command": "PYTHONDONTWRITEBYTECODE=1 " + " ".join(str(a) for a in args),
            "exit_code": 0, "log": log.relative_to(ROOT).as_posix(),
            "sha256": sha(log)}


def main():
    tests = []
    tests.append(run([PYTHON, "-m", "unittest", "discover", "-s", ROOT / "tests", "-v"],
                     ROOT / "cpu-tests.log"))
    sweep = json.loads((ROOT / "diagnostic/provisional-sweep-feasibility.json").read_text())
    if (sweep.get("source_kind") != "authored_synthetic_cpu_opendrive" or
            sweep.get("source_reviewed_native_site") is not False or
            sweep.get("legal_judgment") != "unresolved" or
            sweep.get("source_sha256") != sha(ROOT / "diagnostic-road.xodr") or
            not sweep.get("all_footprints_fit") or
            [item["angle_deg"] for item in sweep["samples"]] != list(range(0, 91, 10))):
        raise ValueError("provisional orientation proof is stale or overstated")
    sweep_log = ROOT / "cpu-sweep-feasibility-tests.log"
    if "Ran 6 tests" not in sweep_log.read_text() or "\nOK\n" not in sweep_log.read_text():
        raise ValueError("provisional sweep tests did not pass")
    tests.append({"command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest "
                  "discover -s " + PREFIX + "/tests -p test_parking_sweep_feasibility.py -v",
                  "exit_code": 0, "log": sweep_log.relative_to(ROOT).as_posix(),
                  "sha256": sha(sweep_log)})
    exception = json.loads((ROOT / "diagnostic/chapter-exception-inventory.json").read_text())
    if (exception.get("format") != "c150041-exported-chapter-exception-inventory-v1" or
            exception.get("frozen_source_sha256") != sha(REPO / "inputs/coverage/branch-sources.json") or
            exception.get("potential_exception", {}).get("law_id") != "LVMC-11-52-070" or
            exception.get("site_exception_status") != "unresolved"):
        raise ValueError("exported Chapter exception inventory stale or overstated")
    exception_log = ROOT / "cpu-chapter-inventory-tests.log"
    if "Ran 2 tests" not in exception_log.read_text() or "\nOK\n" not in exception_log.read_text():
        raise ValueError("Chapter inventory tests did not pass")
    tests.append({"command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest "
                  "discover -s " + PREFIX + "/tests -p test_chapter_exception_inventory.py -v",
                  "exit_code": 0, "log": exception_log.relative_to(ROOT).as_posix(),
                  "sha256": sha(exception_log)})
    for kind in REQUESTS:
        folder = ROOT / "diagnostic" / kind
        fixture = REPO / ".runtime-work" / ("c150041-saved-fixture-v9-" + kind)
        tests.append(run([PYTHON, REPO / "runtime.py", "fixture", "--recipe",
                          folder / "saved-fixture-recipe.json", "--output", fixture],
                         folder / "cpu-fixture-materialize.log"))
        tests.append(run([PYTHON, ROOT / "verify_saved_fixture.py", "--fixture", fixture,
                          "--case", kind, "--output", folder / "cpu-saved-fixture-proof.json"],
                         folder / "cpu-saved-fixture-check.log"))
    tests.append(run([PYTHON, ROOT / "verify_saved_comparisons.py", "--fixture-prefix",
                      REPO / ".runtime-work/c150041-saved-fixture-v9-", "--output",
                      ROOT / "diagnostic/cpu-comparison-fixture-proof.json"],
                     ROOT / "diagnostic/cpu-comparison-fixture-check.log"))
    for kind in REQUESTS:
        folder = ROOT / "diagnostic" / kind
        manifest_path = folder / "diagnostic-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        case = ROOT.name + "__" + kind
        for candidate in ("primary", "fallback1"):
            output = REPO / ".runtime-work" / ("c150041-analysis-bundle-v9-" + candidate + "-" + kind)
            log = (ROOT / ("cpu-" + kind + "-offline-diagnostic.log") if candidate == "primary"
                   else folder / "cpu-fallback1-offline.log")
            tests.append(run([PYTHON, REPO / "runtime.py", "offline", "--manifest", manifest_path,
                              "--case", case, "--candidate", candidate, "--output", output,
                              "--python", PYTHON], log))
            if candidate == "fallback1":
                manifest["cases"][0]["candidates"][0]["offline"] = {
                    "command": tests[-1]["command"], "exit_code": 0,
                    "log": log.relative_to(folder).as_posix(), "log_sha256": sha(log),
                    "construction_sha256": manifest["cases"][0]["candidates"][0]["construction_sha256"]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        receipt = folder / "cpu-compatibility.json"
        log = folder / "cpu-compatibility.log"
        if not json.loads(receipt.read_text()).get("passed"):
            raise ValueError("diagnostic compatibility not passed: " + kind)
        tests.append({"command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python " +
                      PREFIX + "/run_compatibility_diagnostic.py",
                      "exit_code": 0, "log": log.relative_to(ROOT).as_posix(),
                      "sha256": sha(log)})
        saved_receipt = folder / "cpu-process-saved-processing.json"
        saved_log = folder / "cpu-process-saved.log"
        if not json.loads(saved_receipt.read_text()).get("passed"):
            raise ValueError("saved processing not passed: " + kind)
        tests.append({"command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python " +
                      PREFIX + "/run_saved_processing_diagnostic.py",
                      "exit_code": 0, "log": saved_log.relative_to(ROOT).as_posix(),
                      "sha256": sha(saved_log)})
        for candidate in ("primary", "fallback1"):
            draft_log = folder / ("cpu-native-draft-" + candidate + ".log")
            draft = json.loads(draft_log.read_text())
            if (draft.get("offline_passed") is not True or
                    draft.get("candidate_id") != candidate or
                    draft.get("case_id") != case or
                    "c150041-native-draft-v4-" not in draft.get("log", "")):
                raise ValueError("Native draft offline proof missing: " + kind + " " + candidate)
            tests.append({"command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python " +
                          PREFIX + "/run_native_draft_checks.py",
                          "exit_code": 0, "log": draft_log.relative_to(ROOT).as_posix(),
                          "sha256": sha(draft_log)})
    result_path = ROOT / "result.json"
    result = json.loads(result_path.read_text())
    result["tests"] = tests
    result["status"] = "partial"
    result["reason"] = ("Exported Section 11.52.070 angle-parking exception inventory and "
                        "provisional synthetic OpenDRIVE orientation footprint proof pass "
                        "without claiming a reviewed Native site or legal cutoff. All six exact "
                        "synthetic fixture, primary/fallback offline, "
                        "positive/negative pinned compatibility, synthetic saved processing, "
                        "and primary/fallback Native draft offline proofs pass. Genuine "
                        "source-reviewed roadway/activity/Chapter context, source-backed "
                        "judgment sweep, canonical delivery package and local integration "
                        "proof remain worker-owned and incomplete; no physical/legal acceptance claimed.")
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    return len(tests)


if __name__ == "__main__":
    print("refreshed current proof entries:", main())
