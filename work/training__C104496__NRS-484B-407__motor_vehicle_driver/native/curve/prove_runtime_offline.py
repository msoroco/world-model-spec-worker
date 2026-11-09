"""Run four exact curved-grade packages through pinned runtime.py offline."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
CASE = HERE.parents[1]
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    manifest = HERE / "draft-execution-manifest.json"
    token = uuid.uuid4().hex[:12]
    entries = []
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        output = ROOT / ".runtime-work" / f"c104496-curve-{token}-{candidate}"
        run = subprocess.run([sys.executable, str(ROOT / "runtime.py"), "offline",
                              "--manifest", str(manifest), "--case", CASE.name + "__probe_03",
                              "--candidate", candidate, "--output", str(output)],
                             cwd=ROOT, capture_output=True, text=True, timeout=330)
        if run.returncode:
            raise RuntimeError("Pinned curve offline failed: " + run.stdout + run.stderr)
        response = json.loads(run.stdout)
        log = output / "offline.log"
        if not (response["offline_passed"] and response["simulation_started"] is False and
                "Ran 4 tests" in log.read_text() and "\nOK\n" in log.read_text()):
            raise ValueError("Pinned curve offline receipt incomplete")
        selection = json.loads((output / "candidate-selection.json").read_text())
        entries.append({"case_id": CASE.name + "__probe_03", "candidate_id": candidate,
                        "construction_sha256": selection["construction_sha256"],
                        "materialized_dir": str(output.relative_to(ROOT)),
                        "log_sha256": sha(log), "tests": 4, "simulation_started": False,
                        "exit_code": 0})
    receipt = {"format": "c104496-curve-pinned-offline-v1", "manifest_sha256": sha(manifest),
               "entries": entries, "passed": True, "original_native_observed": False,
               "delivery_ready": False}
    (HERE / "pinned-runtime-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return {"passes": len(entries), "tests": sum(x["tests"] for x in entries)}


if __name__ == "__main__":
    print(json.dumps(prove()))
