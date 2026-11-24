"""Rerun exact current-runtime CPU proofs after recording-source changes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
SCRATCH = ROOT / ".runtime-work/c110763-refresh"
VALIDATOR = SCRATCH / "decoder/.lake/build/bin/adapterCheck"
PYTHON = ROOT / ".venv-cpu/bin/python"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    env = os.environ.copy()
    env.update(TMPDIR=str(SCRATCH), SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               PYTHONDONTWRITEBYTECODE="1")
    with log.open("w") as stream:
        result = subprocess.run([str(PYTHON), str(ROOT / "runtime.py"), *map(str, args)],
                                cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"{log.name} exited {result.returncode}: {log.read_text()[-700:]}")
    return {"log": log.name, "log_sha256": sha(log), "exit_code": 0}


def main():
    manifest = json.loads(MANIFEST.read_text())
    output = {}
    for entry, label in zip(manifest["cases"], ("a", "b")):
        case = entry["case_id"]
        for ref in [entry] + entry["candidates"]:
            candidate = ref["id"]
            key = f"{label}-{candidate}"
            offline_output = SCRATCH / f"offline-{key}-v2"
            attempt = SCRATCH / f"compat-{key}-v2"
            saved = SCRATCH / f"saved-{key}-v2"
            offline = run(["offline", "--manifest", MANIFEST, "--case", case,
                           "--candidate", candidate, "--output", offline_output],
                          HERE / f"owner104-offline-{key}-v2.log")
            compatibility = run(["compatibility", "--manifest", MANIFEST, "--case", case,
                                 "--candidate", candidate, "--output", attempt,
                                 "--library", ROOT / "runtime/library", "--validator", VALIDATOR],
                                HERE / f"owner104-compat-{key}-v2.log")
            saved_proof = run(["process-saved", "--manifest", MANIFEST, "--case", case,
                               "--attempt", attempt, "--output", saved,
                               "--library", ROOT / "runtime/library", "--validator", VALIDATOR],
                              HERE / f"owner104-saved-{key}-v2.log")
            receipt_path = attempt / "compatibility.json"
            receipt = json.loads(receipt_path.read_text())
            if not receipt["passed"] or receipt["construction_sha256"] != ref["construction_sha256"]:
                raise ValueError(f"Unbound refreshed compatibility: {key}")
            output[key] = {"case_id": case, "candidate": candidate,
                           "construction_sha256": ref["construction_sha256"],
                           "attempt": str(attempt.relative_to(ROOT)),
                           "saved": str(saved.relative_to(ROOT)),
                           "offline": offline, "compatibility": compatibility,
                           "receipt_sha256": sha(receipt_path),
                           "analysis_sha256": sha(attempt / "compatibility-analysis.log"),
                           "negative_sha256": sha(attempt / "negative-analysis.log"),
                           "negative_removed": receipt["negative_removed"],
                           "saved_proof": saved_proof}
            print(json.dumps({"completed": key, "receipt_sha256": output[key]["receipt_sha256"]}),
                  flush=True)
    proof = {"format": "c110763-owner104-recording-matrix-v1", "passed": True,
             "physical_observation_claimed": False,
             "manifest_sha256": sha(MANIFEST), "paths": output}
    path = HERE / "owner104-recording-matrix-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"proof": path.name, "sha256": sha(path), "paths": len(output)}), flush=True)


if __name__ == "__main__":
    main()
