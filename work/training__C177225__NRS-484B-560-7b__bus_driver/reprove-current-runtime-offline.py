"""Run all sixteen exact selected speed candidates through current offline validation."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "current-runtime-reproof-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            selected = entry if candidate == "primary" else next(
                item for item in entry["candidates"] if item["id"] == candidate)
            output = ROOT / ".runtime-work" / "c177225-current-offline" / suffix / candidate
            command = [sys.executable, str(ROOT / "runtime.py"), "offline", "--manifest",
                       str(MANIFEST), "--case", entry["case_id"], "--candidate", candidate,
                       "--output", str(output), "--python", sys.executable]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log = HERE / "current-runtime-offline" / suffix / (candidate + ".log")
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(run.stdout + run.stderr)
            if run.returncode:
                raise ValueError("Offline failed: " + suffix + "/" + candidate + " " + run.stdout[-800:])
            proof = json.loads(run.stdout)
            if proof.get("offline_passed") is not True or proof.get("case_id") != entry["case_id"] or proof.get("candidate_id") != candidate:
                raise ValueError("Wrong exact offline result: " + suffix + "/" + candidate)
            rows.append({"case_id": entry["case_id"], "candidate_id": candidate,
                         "construction_sha256": selected["construction_sha256"],
                         "log": str(log.relative_to(HERE)), "log_sha256": sha(log)})
            print(suffix, candidate, "offline passed", flush=True)
    if len(rows) != 8:
        raise ValueError("Eight exact chains required")
    path = HERE / "current-runtime-offline-reproof.json"
    path.write_text(json.dumps({"format": "c177225-current-offline-v1",
                                "manifest_sha256": sha(MANIFEST), "rows": rows,
                                "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"chains": len(rows), "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
