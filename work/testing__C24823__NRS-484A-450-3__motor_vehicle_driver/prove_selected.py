"""Run all ten exact source-gated offline and compatibility CPU checks."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.draft.json"
SCRATCH = REPO / ".runtime-work/c24823/selected"
VALIDATOR = REPO / ".runtime-work/c130864-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main():
    if REPO / ".runtime-work" not in Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve().parents:
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    if REPO / ".runtime-work" not in Path(os.environ["TMPDIR"]).resolve().parents:
        raise ValueError("TMPDIR must be under .runtime-work")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    offline_rows, compatibility_rows = [], []
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    for entry in entries:
        cid = entry["case_id"]
        tag = cid.split("__")[-1]
        for candidate in ("primary", "fallback1"):
            selected = entry if candidate == "primary" else entry["candidates"][0]
            dest = SCRATCH / tag / candidate
            if dest.exists():
                shutil.rmtree(dest)
            offline = dest / "offline"
            command = [sys.executable, str(REPO / "runtime.py"), "offline",
                "--manifest", str(MANIFEST), "--case", cid, "--candidate", candidate,
                "--output", str(offline), "--python", sys.executable]
            completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            folder = ROOT / "cases" / tag
            log = folder / ("proof-offline-" + candidate + ".log")
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text((completed.stdout + completed.stderr).rstrip() + "\n", encoding="utf-8")
            off_row = {"case_id": cid, "candidate": candidate,
                "construction_sha256": selected["construction_sha256"],
                "command": " ".join(command), "exit_code": completed.returncode,
                "log": log.relative_to(ROOT).as_posix(), "log_sha256": sha(log)}
            offline_rows.append(off_row)
            if completed.returncode:
                raise RuntimeError("offline failed: " + cid + " " + candidate + " " + log.read_text()[-1000:])
            compat = dest / "compatibility"
            command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                "--manifest", str(MANIFEST), "--case", cid, "--candidate", candidate,
                "--output", str(compat), "--library", str(REPO / "runtime/library"),
                "--validator", str(VALIDATOR)]
            completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            if completed.returncode:
                raise RuntimeError("compatibility failed: " + cid + " " + candidate + " " +
                                   (completed.stdout + completed.stderr)[-1500:])
            receipt = json.loads((compat / "compatibility.json").read_text(encoding="utf-8"))
            prefix = "proof-compatibility-" + candidate
            for source, target in (("compatibility.json", prefix + ".json"),
                                   ("compatibility-analysis.log", prefix + "-analysis.log"),
                                   ("negative-analysis.log", prefix + "-negative.log")):
                (folder / target).write_bytes((compat / source).read_bytes())
            receipt_path = folder / (prefix + ".json")
            compatibility_rows.append({"case_id": cid, "candidate": candidate,
                "construction_sha256": receipt["construction_sha256"],
                "command": " ".join(command), "exit_code": 0,
                "receipt": receipt_path.relative_to(ROOT).as_posix(), "receipt_sha256": sha(receipt_path),
                "positive_log": (folder / (prefix + "-analysis.log")).relative_to(ROOT).as_posix(),
                "negative_log": (folder / (prefix + "-negative.log")).relative_to(ROOT).as_posix()})
            print(tag, candidate, "offline and compatibility passed", flush=True)
    write(ROOT / "cpu-offline-proofs.json", offline_rows)
    write(ROOT / "cpu-compatibility-proofs.json", compatibility_rows)
    if len(offline_rows) != 10 or len(compatibility_rows) != 10:
        raise RuntimeError("ten exact selected candidate proofs required")


if __name__ == "__main__":
    main()
