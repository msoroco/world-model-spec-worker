"""Run every C10365 construction through the pinned runtime offline CLI."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    token = uuid.uuid4().hex[:12]
    manifest = HERE / "draft-execution-manifest.json"
    entries = []
    for suffix in ("probe_a", "probe_b"):
        case_id = CASE.name + "__" + suffix
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            output = ROOT / ".runtime-work" / f"c10365-officer-{token}-{suffix}-{candidate}"
            run = subprocess.run([
                sys.executable, str(ROOT / "runtime.py"), "offline",
                "--manifest", str(manifest), "--case", case_id,
                "--candidate", candidate, "--output", str(output)],
                cwd=ROOT, capture_output=True, text=True, timeout=330)
            if run.returncode:
                raise RuntimeError("Pinned offline failed: " + run.stdout + run.stderr)
            response = json.loads(run.stdout)
            log = output / "offline.log"
            if not (response["offline_passed"] and response["simulation_started"] is False
                    and "Ran 3 tests" in log.read_text() and "\nOK\n" in log.read_text()):
                raise ValueError("Pinned offline receipt incomplete")
            selection = json.loads((output / "candidate-selection.json").read_text())
            entries.append({
                "case_id": case_id, "candidate_id": candidate,
                "construction_sha256": selection["construction_sha256"],
                "materialized_dir": str(output.relative_to(ROOT)),
                "log_sha256": sha(log), "tests": 3,
                "simulation_started": False, "exit_code": 0})
    receipt = {
        "format": "c10365-officer-pinned-offline-v1",
        "manifest_sha256": sha(manifest), "entries": entries,
        "passed": True, "original_native_observed": False, "delivery_ready": False}
    (HERE / "pinned-runtime-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    receipt = prove()
    print(json.dumps({"passes": len(receipt["entries"]),
                      "tests": sum(row["tests"] for row in receipt["entries"])}))
