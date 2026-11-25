"""Run nine exact selected constructions through the public CPU offline command."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c104496-selected-offline-v3"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_log(text):
    return "\n".join(line.rstrip() for line in text.rstrip().splitlines()) + "\n"


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = HERE / "selected-construction-manifest.json"
    entries = json.loads(manifest.read_text())["cases"]
    rows = []
    for entry in entries:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1", "fallback2"):
            target = SCRATCH / (suffix + "-" + candidate)
            command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"),
                       "offline", "--manifest", str(manifest), "--case", case_id,
                       "--candidate", candidate, "--output", str(target),
                       "--python", str(ROOT / ".venv-cpu/bin/python")]
            env = dict(os.environ, TMPDIR=str(SCRATCH),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
                       PYTHONDONTWRITEBYTECODE="1")
            run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                 text=True, timeout=300)
            if run.returncode:
                raise ValueError(suffix + " " + candidate + " offline failed: " +
                                 run.stderr[-1200:] + "\n" +
                                 ((target / "offline.log").read_text()[-1200:]
                                  if (target / "offline.log").is_file() else ""))
            source = target / "offline.log"
            log = HERE / "selected-offline" / (suffix + "-" + candidate + ".log")
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(clean_log(source.read_text()))
            selected = entry if candidate == "primary" else next(
                item for item in entry["candidates"] if item["id"] == candidate)
            rows.append({"case_id": case_id, "candidate_id": candidate,
                         "construction_sha256": selected["construction_sha256"],
                         "command": " ".join(command), "exit_code": 0,
                         "log": str(log.relative_to(HERE)), "log_sha256": sha(log)})
            print(json.dumps({"case": suffix, "candidate": candidate,
                              "offline_passed": True}), flush=True)
    proof = {"format": "c104496-selected-offline-proof-v1", "cases": rows,
             "passed": len(rows) == 9, "original_native_executed": False}
    path = HERE / "selected-offline-proof.json"
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": proof["passed"], "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
