"""Prove exact synthetic physical, lifecycle and delivery audit protocols."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess

from prove_saved import source_attempt


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c422976-owner"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, log, expected=0):
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH),
               MPLCONFIGDIR=str(SCRATCH / "mpl"), PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(REPO / "runtime") + os.pathsep +
                          str(REPO / "runtime/scenario_pipeline") + os.pathsep + str(HERE))
    process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    content = (process.stdout + process.stderr).rstrip() + "\n"
    log.write_text(content, encoding="utf-8")
    if process.returncode != expected:
        raise ValueError("post compatibility proof returned %d: %s: %s" %
                         (process.returncode, log, content[-1000:]))
    return {"command": " ".join(command), "exit_code": process.returncode,
            "log": str(log.relative_to(HERE)), "log_sha256": digest(log)}


def one(entry):
    case_id = entry["case_id"]
    suffix = case_id.rsplit("__", 1)[-1]
    folder = HERE / "cases" / suffix
    attempt = source_attempt(case_id, suffix)
    saved_log = folder / "cpu-saved.log"
    saved = json.loads(saved_log.read_text())
    if saved.get("case_id") != case_id or not saved.get("passed"):
        raise ValueError("current saved-only proof missing: " + suffix)
    fixtures = []
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        output = SCRATCH / ("post-" + suffix + "-" + kind + ".json")
        output.unlink(missing_ok=True)
        command = [str(REPO / ".venv-cpu/bin/python"), str(HERE / "prove_physical.py"),
                   "--case", case_id, "--kind", kind, "--attempt", str(attempt),
                   "--output", str(output)]
        proof = execute(command, folder / ("physical-" + kind + ".log"))
        target = folder / ("physical-" + kind + ".json")
        target.write_bytes(output.read_bytes())
        proof.update(kind=kind, result=str(target.relative_to(HERE)),
                     result_sha256=digest(target))
        fixtures.append(proof)
    life = execute([str(REPO / ".venv-cpu/bin/python"), str(HERE / "prove_lifecycle.py"),
                    "--case", case_id, "--attempt", str(attempt),
                    "--saved-receipt", str(saved_log)], folder / "physical-lifecycle.log")
    life["events"] = EVENTS
    positive = execute([str(REPO / ".venv-cpu/bin/python"),
                        str(HERE / "prove_delivery_contract.py"), "--case", case_id,
                        "--mode", "diagnostic-positive"],
                       folder / "delivery-diagnostic-positive.log")
    negative = execute([str(REPO / ".venv-cpu/bin/python"),
                        str(HERE / "prove_delivery_contract.py"), "--case", case_id,
                        "--mode", "delivery-negative"],
                       folder / "delivery-delivery-negative.log", expected=1)
    if "released original school-lane Native attempt required" not in (HERE / negative["log"]).read_text():
        raise ValueError("delivery negative did not reject unreleased attempt")
    preparation = {"format": "worker-physical-preparation", "case_id": case_id,
                   "construction_sha256": digest(HERE / entry["construction"]),
                   "fixtures": fixtures, "lifecycle": life, "diagnostic_fixture": True,
                   "physical_acceptance_claimed": False}
    path = folder / "physical-preparation.json"
    path.write_text(json.dumps(preparation, indent=2, sort_keys=True) + "\n")
    return {"case_id": case_id, "physical_preparation": str(path.relative_to(HERE)),
            "physical_preparation_sha256": digest(path), "delivery_positive": positive,
            "delivery_negative": negative}


def main():
    entries = json.loads((HERE / "diagnostic-execution-manifest.json").read_text())["cases"]
    if len(entries) != 15:
        raise ValueError("all selected exact cases required")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(one, entries))
    (HERE / "post-compat-proof-summary.json").write_text(
        json.dumps({"format": "c422976-post-compat-proof-summary-v1", "cases": results},
                   indent=2, sort_keys=True) + "\n")
    print("Proved", len(results), "exact physical/lifecycle/delivery CPU protocols")


if __name__ == "__main__":
    main()
