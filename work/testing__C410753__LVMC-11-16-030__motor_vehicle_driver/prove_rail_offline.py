"""Run selected construction checks for primary and fallback railway cases."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def one(entry, candidate):
    case = entry["case_id"]
    key = case.removeprefix(HERE.name + "__")
    output = REPO / ".runtime-work" / f"c410753-offline-{key}-{candidate}"
    command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
               "offline", "--manifest", str(MANIFEST), "--case", case,
               "--candidate", candidate, "--output", str(output)]
    done = subprocess.run(command, cwd=REPO, env=os.environ,
                          capture_output=True, text=True)
    log = HERE / f"cpu-offline-{key}-{candidate}.log"
    if (output / "offline.log").is_file():
        log.write_text((output / "offline.log").read_text().rstrip() + "\n")
    else:
        log.write_text((done.stdout + done.stderr).rstrip() + "\n")
    if done.returncode or not (output / "offline.log").is_file():
        raise RuntimeError(f"rail offline {key} {candidate}: " + log.read_text()[-1500:])
    construction_hash = entry["construction_sha256"] if candidate == "primary" else next(
        row["construction_sha256"] for row in entry["candidates"]
        if row["id"] == candidate)
    return case, candidate, {"command": " ".join(command), "exit_code": 0,
                            "construction_sha256": construction_hash,
                            "log": log.name, "log_sha256": sha(log)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    tasks = [(entry, candidate) for entry in manifest["cases"]
             for candidate in ("primary", "fallback1")]
    bindings = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(one, entry, candidate) for entry, candidate in tasks]
        for future in as_completed(futures):
            case, candidate, proof = future.result()
            bindings[(case, candidate)] = proof
            print("offline", case, candidate, "passed", flush=True)
    current = json.loads(MANIFEST.read_text())
    for entry in current["cases"]:
        entry["offline"] = bindings[(entry["case_id"], "primary")]
        for candidate in entry["candidates"]:
            candidate["offline"] = bindings[(entry["case_id"], candidate["id"])]
    MANIFEST.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
