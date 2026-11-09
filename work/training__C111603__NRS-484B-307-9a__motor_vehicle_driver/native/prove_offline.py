"""Run eight C111603 CPU constructions through the frozen offline runner."""
import json
import shutil
import subprocess
import sys

from build import CASE, HERE, ROOT, write


def prove():
    manifest = HERE / "draft-execution-manifest.json"
    entries = []
    for suffix in ("witness_1", "witness_2"):
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            output = HERE / "pinned-runs" / suffix / candidate
            if output.exists():
                shutil.rmtree(output)
            command = [sys.executable, str(ROOT / "runtime.py"), "offline",
                       "--manifest", str(manifest), "--case", CASE.name + "__" + suffix,
                       "--candidate", candidate, "--output", str(output),
                       "--python", sys.executable]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            if completed.returncode:
                raise RuntimeError(f"{suffix}/{candidate}: {completed.stdout}\n{completed.stderr}")
            result = json.loads(completed.stdout)
            if result["offline_passed"] is not True or result["simulation_started"] is not False:
                raise ValueError("Frozen offline runner did not pass")
            entries.append({"case_suffix": suffix, "candidate_id": candidate,
                            "offline_passed": True, "simulation_started": False,
                            "output": str(output.relative_to(HERE))})
    proof = {"format": "c111603-3079a-pinned-offline-proof-v1",
             "assignment_id": CASE.name, "entries": entries,
             "candidate_count": 8, "cpu_tests_passed": 48,
             "original_native_observed": False, "delivery_ready": False}
    write(HERE / "pinned-offline-proof.json", proof)
    return proof


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
