"""Run every unselected 600-frame exact bundle through pinned runtime.py offline."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / ".venv-cpu/bin/python"
MANIFEST = HERE / "draft-execution-manifest-600.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    manifest = json.loads(MANIFEST.read_text())
    scratch = Path(tempfile.mkdtemp(prefix="c110454-offline-600-", dir=ROOT / ".runtime-work"))
    results = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        refs = [entry] + entry["candidates"]
        for ref in refs:
            candidate = ref["id"]
            output = scratch / (suffix + "-" + candidate)
            command = [str(PYTHON), str(ROOT / "runtime.py"), "offline", "--manifest",
                       str(MANIFEST), "--case", entry["case_id"], "--candidate", candidate,
                       "--output", str(output), "--python", str(PYTHON)]
            process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, timeout=300)
            if process.returncode:
                raise RuntimeError(f"Offline {suffix}/{candidate} failed: {process.stdout}")
            receipt = json.loads(process.stdout)
            log = output / "offline.log"
            if receipt.get("offline_passed") is not True or \
                    "Ran 5 tests" not in log.read_text() or not log.read_text().rstrip().endswith("OK"):
                raise ValueError("Exact offline unit-test proof differs")
            construction = HERE / ref["construction"]
            if sha(construction) != ref["construction_sha256"]:
                raise ValueError("Exact construction hash differs")
            config = json.loads((output / "config.json").read_text())
            if config["duration_s"] != 30 or config["rate_hz"] != 20 or \
                    config["engineering_knobs"]["duration_s"] != 30:
                raise ValueError("Long duration source contract differs")
            results.append({"case": suffix, "candidate": candidate,
                            "construction_sha256": ref["construction_sha256"],
                            "offline_log_sha256": sha(log), "duration_s": 30,
                            "rate_hz": 20, "planned_frames": 600,
                            "native_executed": False})
            print(suffix, candidate, "offline passed", flush=True)
    proof = {"format": "c110454-unselected-600-offline-proof-v1", "passed": True,
             "assignment_id": HERE.name, "manifest_sha256": sha(MANIFEST),
             "results": results, "scope": "offline exact construction only; no CARLA or saved processing"}
    target = HERE / "draft-offline-600-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "bundles": len(results),
                      "proof_sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    run()
