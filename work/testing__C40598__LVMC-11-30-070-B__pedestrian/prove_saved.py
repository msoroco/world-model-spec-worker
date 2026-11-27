"""Exercise selected saved-only processing on each exact synthetic Native-shaped attempt."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = ROOT / "execution-manifest.draft.json"
    rows = []
    for entry in json.loads(manifest.read_text())["cases"]:
        cid = entry["case_id"]
        short = cid.split("__")[-1]
        source = REPO / ".runtime-work/c40598-owner/compat-selected" / short / "primary"
        output = REPO / ".runtime-work/c40598-owner/saved-selected" / short
        if output.exists():
            shutil.rmtree(output)
        command = [sys.executable, str(REPO / "runtime.py"), "process-saved",
            "--manifest", str(manifest), "--case", cid,
            "--attempt", str(source), "--output", str(output),
            "--library", str(REPO / "runtime/library"),
            "--validator", str(REPO / ".runtime-work/c150911-decoder/.lake/build/bin/adapterCheck")]
        completed = subprocess.run(command, cwd=REPO, env=os.environ,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log = ROOT / "cases" / short / "proof-saved-only.log"
        log.write_text(completed.stdout.rstrip() + "\n")
        receipt = output / "v0001/processing.json"
        if completed.returncode == 0:
            value = json.loads(receipt.read_text())
            if not (value["passed"] and value["recorded_only"] and
                    value["originals_preserved"] and not value["missing_evidence"] and
                    not value["physical_acceptance_claimed"] and
                    not value["legal_acceptance_claimed"]):
                raise ValueError("saved-only provenance/closure differs: " + cid)
        rows.append({"case_id": cid, "exit_code": completed.returncode,
            "command": " ".join(command), "log": str(log.relative_to(ROOT)),
            "log_sha256": sha(log), "receipt_sha256": sha(receipt) if receipt.is_file() else None})
        print(short, completed.returncode, flush=True)
    (ROOT / "cpu-saved-proofs.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    if any(row["exit_code"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
