"""Run all eight exact C104496 CPU packages through pinned runtime.py offline."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
from build import CASES, HERE, POLICIES

CASE = HERE.parents[1]
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    token = uuid.uuid4().hex[:12]
    manifest = HERE / "draft-execution-manifest.json"
    entries = []
    for suffix in CASES:
        case_id = CASE.name + "__" + suffix
        for candidate in POLICIES:
            output = ROOT / ".runtime-work" / f"c104496-crest-{token}-{suffix}-{candidate}"
            run = subprocess.run([sys.executable, str(ROOT / "runtime.py"), "offline",
                                  "--manifest", str(manifest), "--case", case_id,
                                  "--candidate", candidate, "--output", str(output)],
                                 cwd=ROOT, capture_output=True, text=True, timeout=330)
            if run.returncode:
                raise RuntimeError("Pinned offline failed: " + run.stdout + run.stderr)
            response = json.loads(run.stdout)
            log = output / "offline.log"
            if not (response["offline_passed"] and response["simulation_started"] is False and
                    "Ran 4 tests" in log.read_text() and "\nOK\n" in log.read_text()):
                raise ValueError("Pinned offline receipt incomplete")
            selection = json.loads((output / "candidate-selection.json").read_text())
            entries.append({"case_id": case_id, "candidate_id": candidate,
                            "construction_sha256": selection["construction_sha256"],
                            "materialized_dir": str(output.relative_to(ROOT)),
                            "log_sha256": sha(log), "tests": 4, "simulation_started": False,
                            "exit_code": 0})
    receipt = {"format": "c104496-crest-pinned-offline-v1", "manifest_sha256": sha(manifest),
               "entries": entries, "passed": True, "original_native_observed": False,
               "delivery_ready": False}
    (HERE / "pinned-runtime-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return {"passes": len(entries), "tests": sum(x["tests"] for x in entries)}


if __name__ == "__main__":
    print(json.dumps(prove()))
