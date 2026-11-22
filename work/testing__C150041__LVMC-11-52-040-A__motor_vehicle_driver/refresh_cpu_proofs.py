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
    for kind in REQUESTS:
        folder = ROOT / "diagnostic" / kind
        fixture = REPO / ".runtime-work" / ("c150041-saved-fixture-v4-" + kind)
        tests.append(run([PYTHON, REPO / "runtime.py", "fixture", "--recipe",
                          folder / "saved-fixture-recipe.json", "--output", fixture],
                         folder / "cpu-fixture-materialize.log"))
        tests.append(run([PYTHON, ROOT / "verify_saved_fixture.py", "--fixture", fixture,
                          "--case", kind, "--output", folder / "cpu-saved-fixture-proof.json"],
                         folder / "cpu-saved-fixture-check.log"))
    tests.append(run([PYTHON, ROOT / "verify_saved_comparisons.py", "--fixture-prefix",
                      REPO / ".runtime-work/c150041-saved-fixture-v4-", "--output",
                      ROOT / "diagnostic/cpu-comparison-fixture-proof.json"],
                     ROOT / "diagnostic/cpu-comparison-fixture-check.log"))
    for kind in REQUESTS:
        folder = ROOT / "diagnostic" / kind
        manifest_path = folder / "diagnostic-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        case = ROOT.name + "__" + kind
        for candidate in ("primary", "fallback1"):
            output = REPO / ".runtime-work" / ("c150041-analysis-bundle-v4-" + candidate + "-" + kind)
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
    result_path = ROOT / "result.json"
    result = json.loads(result_path.read_text())
    result["tests"] = tests
    result["status"] = "partial"
    result["reason"] = ("All six exact synthetic saved fixture, primary/fallback offline, "
                        "and positive/negative pinned compatibility proofs pass. Genuine "
                        "source-reviewed roadway/activity/Chapter context, full semantic "
                        "judgment sweep, process-saved delivery receipts and Native delivery "
                        "remain worker-owned and incomplete; no physical/legal acceptance claimed.")
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    return len(tests)


if __name__ == "__main__":
    print("refreshed current proof entries:", main())
