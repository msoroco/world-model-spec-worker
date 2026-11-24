"""Run current pinned runtime offline for all twelve unselected source-bound requests."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
MANIFEST = CASE / "draft-execution-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("status") != "draft_not_selected" or len(manifest.get("cases", [])) != 3:
        raise ValueError("Expected three unselected draft cases")
    run_root = ROOT / ".runtime-work" / ("c102951-pinned-sweep-" + uuid.uuid4().hex[:12])
    run_root.mkdir(parents=True)
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(run_root / "adapter")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    results = []
    for entry in manifest["cases"]:
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            destination = run_root / (entry["case_id"].split("__")[-1] + "-" + candidate)
            command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--candidate", candidate, "--output", str(destination)]
            process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
            if process.returncode:
                raise RuntimeError(f"Pinned offline failed for {entry['case_id']} {candidate}: {process.stderr[-1200:]}")
            response = json.loads(process.stdout)
            if response.get("offline_passed") is not True or response.get("simulation_started") is not False:
                raise ValueError("Pinned offline response changed")
            log = destination / "offline.log"
            selection = json.loads((destination / "candidate-selection.json").read_text())
            if selection["candidate_id"] != candidate or selection["case_id"] != entry["case_id"]:
                raise ValueError("Pinned candidate identity changed")
            results.append({"case_id": entry["case_id"], "candidate_id": candidate,
                            "construction_sha256": selection["construction_sha256"],
                            "selection_sha256": sha(destination / "candidate-selection.json"),
                            "offline_log_sha256": sha(log),
                            "test_count": log.read_text().count("Ran 3 tests"),
                            "offline_passed": True, "native_executed": False})
    if len(results) != 12 or any(item["test_count"] != 1 for item in results):
        raise ValueError("Incomplete pinned offline sweep")
    proof = {"format": "c102951-unselected-pinned-offline-sweep-v1",
             "assignment_id": CASE.name, "passed": True, "diagnostic_only": True,
             "manifest_sha256": sha(MANIFEST), "run_root": str(run_root.relative_to(ROOT)),
             "results": results, "selected_delivery": False, "original_native_observed": False}
    path = CASE / "runtime-draft/pinned-offline-sweep-proof.json"
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "count": len(results), "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
