"""Saved-only positive and missing-original-map diagnostic checks."""

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
    rows = []
    for case in json.loads((ROOT / "case-plan.json").read_text())["cases"]:
        cid = case["case_id"]
        short = cid.split("__")[-1]
        original = REPO / ".runtime-work/c130864-compat-selected" / short / "primary"
        folder = ROOT / "cases" / short
        for variant in ("positive", "missing-map"):
            attempt = REPO / ".runtime-work/c130864-saved-source-final" / short / variant
            if attempt.exists():
                shutil.rmtree(attempt)
            shutil.copytree(original, attempt)
            selection_path = attempt / "candidate-selection.json"
            selection = json.loads(selection_path.read_text())
            selection["manifest_sha256"] = manifest_sha
            selection_path.write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n")
            if variant == "missing-map":
                (attempt / "original-map.json").unlink()
            output = REPO / ".runtime-work/c130864-saved-final" / short / variant
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                "process-saved", "--manifest", str(MANIFEST), "--case", cid,
                "--attempt", str(attempt), "--output", str(output),
                "--library", str(REPO / "runtime/library"), "--validator",
                str(REPO / ".runtime-work/c130864-decoder/.lake/build/bin/adapterCheck")]
            completed = subprocess.run(command, cwd=REPO, env=os.environ,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True)
            log = folder / ("proof-saved-" + variant + ".log")
            log.write_text(completed.stdout.rstrip() + "\n")
            versions = sorted(output.glob("v*/processing.json"))
            receipt = json.loads(versions[-1].read_text()) if versions else None
            row = {"case_id": cid, "variant": variant, "manifest_sha256": manifest_sha,
                   "command": " ".join(command), "exit_code": completed.returncode,
                   "log": str(log.relative_to(ROOT)), "log_sha256": sha(log),
                   "receipt": str(versions[-1].relative_to(REPO)) if versions else None,
                   "receipt_sha256": sha(versions[-1]) if versions else None,
                   "missing_evidence": receipt.get("missing_evidence") if receipt else None,
                   "originals_preserved": receipt.get("originals_preserved") if receipt else None}
            rows.append(row)
            print(short, variant, completed.returncode, row["missing_evidence"], flush=True)
    (ROOT / "cpu-saved-proofs.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    if len(rows) != 12 or any(row["exit_code"] or not row["originals_preserved"] or
                              row["missing_evidence"] != (row["variant"] == "missing-map")
                              for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
