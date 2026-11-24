"""Recheck every exact unselected signal construction on the pinned CPU runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-execution-manifest.json"
SCRATCH = ROOT / ".runtime-work" / "c329610-current-offline"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    if manifest["assignment_id"] != HERE.name or len(manifest["cases"]) != 6:
        raise ValueError("Exact six-case draft signal manifest required")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "tmp").mkdir(exist_ok=True)
    env = dict(os.environ)
    env["TMPDIR"] = str(SCRATCH / "tmp")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH / "runtime-output")
    env["MPLCONFIGDIR"] = str(SCRATCH / "matplotlib")
    rows = []
    for case in manifest["cases"]:
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            suffix = case["case_id"].split("__")[-1]
            label = suffix + "-" + candidate
            output = SCRATCH / label
            if output.exists():
                raise ValueError("Keep prior offline attempt; remove only ignored scratch after review: " + label)
            command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"),
                       "offline", "--manifest", str(MANIFEST), "--case", case["case_id"],
                       "--candidate", candidate, "--output", str(output),
                       "--python", str(ROOT / ".venv-cpu/bin/python")]
            run = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                 capture_output=True, timeout=300)
            if run.returncode:
                raise RuntimeError(label + " offline failed: " + run.stderr[-1000:])
            report = json.loads(run.stdout)
            if report["case_id"] != case["case_id"] or report["candidate_id"] != candidate or not report["offline_passed"]:
                raise ValueError("Pinned offline reported another case or failed")
            log = output / "offline.log"
            content = log.read_text()
            if "Ran 4 tests" not in content or "OK" not in content:
                raise ValueError("Exact bundle tests incomplete: " + label)
            selected = case if candidate == "primary" else next(c for c in case["candidates"] if c["id"] == candidate)
            construction = HERE / selected["construction"]
            if sha(construction) != selected["construction_sha256"]:
                raise ValueError("Draft construction hash changed: " + label)
            rows.append({"case_id": case["case_id"], "candidate_id": candidate,
                         "construction_sha256": selected["construction_sha256"],
                         "offline_log_sha256": sha(log), "tests_passed": 4})
    receipt = {"format": "c329610-current-pinned-draft-offline-v1",
               "assignment_id": HERE.name, "runtime_source_manifest_sha256": sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json"),
               "draft_manifest_sha256": sha(MANIFEST), "cases": 6, "candidates": 24,
               "tests_passed": 96, "simulation_started": False,
               "selection_status": "draft_not_selected", "rows": rows}
    path = HERE / "current-pinned-offline-proof.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": str(path.relative_to(ROOT)), "sha256": sha(path),
                      "candidates": len(rows), "tests_passed": 96}))


if __name__ == "__main__":
    main()
