"""Run pinned positive and missing-source checks against the selected manifest."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_sha = sha(MANIFEST)
    entries = json.loads(MANIFEST.read_text())["cases"]
    rows = []
    for entry in entries:
        cid = entry["case_id"]
        short = cid.split("__")[-1]
        folder = ROOT / "cases" / short
        for candidate in ("primary", "fallback1"):
            output = REPO / ".runtime-work/c130864-compat-canonical" / short / candidate
            if output.exists():
                shutil.rmtree(output)
            command = [str(REPO / ".venv-cpu/bin/python"),
                str(ROOT / "run_compat_deterministic.py"), "--manifest", str(MANIFEST),
                "--case", cid, "--candidate", candidate, "--output", str(output),
                "--library", str(REPO / "runtime/library"), "--validator",
                str(REPO / ".runtime-work/c130864-decoder/.lake/build/bin/adapterCheck")]
            completed = subprocess.run(command, cwd=REPO, env=os.environ,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True)
            stem = "proof-canonical-compat-" + candidate
            log = folder / (stem + ".log")
            log.write_text(completed.stdout.rstrip() + "\n")
            row = {"case_id": cid, "candidate": candidate,
                   "manifest_sha256": manifest_sha, "command": " ".join(command),
                   "exit_code": completed.returncode, "log": str(log.relative_to(ROOT)),
                   "log_sha256": sha(log)}
            if completed.returncode == 0:
                for name, suffix in (("compatibility.json", ".json"),
                                     ("compatibility-analysis.log", "-analysis.log"),
                                     ("negative-analysis.log", "-negative.log")):
                    dest = folder / (stem + suffix)
                    dest.write_bytes((output / name).read_bytes())
                    row[name + "_path"] = str(dest.relative_to(ROOT))
                    row[name + "_sha256"] = sha(dest)
            rows.append(row)
            print(short, candidate, completed.returncode, flush=True)
    (ROOT / "cpu-canonical-compatibility-proofs.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n")
    if len(rows) != 12 or any(row["exit_code"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
