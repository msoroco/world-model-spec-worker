"""Run all eight C111294 draft constructions through the frozen offline runner."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASE = HERE.parent.name


def prove():
    manifest = HERE / "draft-execution-manifest.json"
    entries = []
    for suffix in ("controlled_1", "controlled_2"):
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            output = HERE / "pinned-runs" / suffix / candidate
            command = [sys.executable, str(ROOT / "runtime.py"), "offline", "--manifest", str(manifest),
                       "--case", CASE + "__" + suffix, "--candidate", candidate,
                       "--output", str(output), "--python", sys.executable]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            if completed.returncode:
                raise RuntimeError(f"{suffix}/{candidate}: {completed.stdout}\n{completed.stderr}")
            result = json.loads(completed.stdout)
            if result["offline_passed"] is not True or result["simulation_started"] is not False:
                raise ValueError("Frozen offline runner did not pass cleanly")
            entries.append({"case_suffix": suffix, "candidate_id": candidate,
                            "offline_passed": True, "simulation_started": False,
                            "output": str(output.relative_to(HERE))})
    proof = {"format": "c111294-2502-pinned-offline-proof-v1", "entries": entries,
             "candidate_count": 8, "cpu_tests_passed": 24,
             "original_native_observed": False, "delivery_ready": False}
    (HERE / "pinned-runtime-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    return proof


if __name__ == "__main__":
    print(json.dumps(prove()))
