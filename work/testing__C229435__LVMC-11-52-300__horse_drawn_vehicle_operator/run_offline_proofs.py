"""Run the pinned runtime offline check for each selected exact bundle."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = REPO / ".runtime-work" / "c229435-offline" / "batch-v5"
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        destination = root / suffix
        if destination.exists():
            if (destination / "offline.log").is_file():
                existing = (destination / "offline.log").read_text()
                if "OK" not in existing:
                    raise ValueError("retained offline attempt failed: " + suffix)
            else:
                raise ValueError("retained incomplete offline attempt: " + suffix)
        else:
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                       "offline", "--manifest", str(manifest_path), "--case", entry["case_id"],
                       "--output", str(destination), "--python", str(REPO / ".venv-cpu/bin/python")]
            subprocess.run(command, cwd=REPO, env=os.environ, check=True)
        text = (destination / "offline.log").read_text().rstrip() + "\n"
        proof = ROOT / ("proof-offline-" + suffix + ".log")
        proof.write_text(text)
        entry["offline"] = {
            "exit_code": 0, "construction_sha256": entry["construction_sha256"],
            "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + ASSIGNMENT
                       + "/execution-manifest.json --case " + entry["case_id"]
                       + " --output .runtime-work/c229435-offline/batch-v5/" + suffix
                       + " --python $PWD/.venv-cpu/bin/python",
            "log": proof.name, "log_sha256": sha(proof),
        }
        print("offline pass", suffix, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
