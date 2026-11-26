"""Saved-only positive and missing-original-island-map diagnostic checks."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c130282"
VALIDATOR = REPO / ".runtime-work/c130864-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if REPO / ".runtime-work" not in Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve().parents:
        raise ValueError("output root must be under .runtime-work")
    manifest_sha = sha(MANIFEST)
    rows = []
    for case in json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))["cases"]:
        cid = case["case_id"]
        tag = cid.split("__")[-1]
        original = SCRATCH / "selected" / tag / "primary/compatibility"
        folder = ROOT / "cases" / tag
        for variant in ("positive", "missing-map"):
            attempt = SCRATCH / "saved-source" / tag / variant
            if attempt.exists():
                shutil.rmtree(attempt)
            shutil.copytree(original, attempt)
            selection_path = attempt / "candidate-selection.json"
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
            selection["manifest_sha256"] = manifest_sha
            selection_path.write_text(json.dumps(selection, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            if variant == "missing-map":
                (attempt / "original-map.json").unlink()
            output = SCRATCH / "saved-output" / tag / variant
            if output.exists():
                shutil.rmtree(output)
            command = [sys.executable, str(REPO / "runtime.py"), "process-saved",
                "--manifest", str(MANIFEST), "--case", cid, "--attempt", str(attempt),
                "--output", str(output), "--library", str(REPO / "runtime/library"),
                "--validator", str(VALIDATOR)]
            completed = subprocess.run(command, cwd=REPO, env=os.environ,
                                       capture_output=True, text=True)
            log = folder / ("proof-saved-" + variant + ".log")
            log.write_text((completed.stdout + completed.stderr).rstrip() + "\n", encoding="utf-8")
            versions = sorted(output.glob("v*/processing.json"))
            saved_receipt = folder / ("proof-saved-" + variant + ".json")
            receipt = json.loads(versions[-1].read_text(encoding="utf-8")) if versions else None
            if receipt:
                saved_receipt.write_bytes(versions[-1].read_bytes())
            row = {"case_id": cid, "variant": variant, "manifest_sha256": manifest_sha,
                "command": " ".join(command), "exit_code": completed.returncode,
                "log": log.relative_to(ROOT).as_posix(), "log_sha256": sha(log),
                "receipt": saved_receipt.relative_to(ROOT).as_posix() if receipt else None,
                "receipt_sha256": sha(saved_receipt) if receipt else None,
                "missing_evidence": receipt.get("missing_evidence") if receipt else None,
                "originals_preserved": receipt.get("originals_preserved") if receipt else None}
            rows.append(row)
            print(tag, variant, completed.returncode, row["missing_evidence"], flush=True)
    (ROOT / "cpu-saved-proofs.json").write_text(json.dumps(rows, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if len(rows) != 8 or any(row["exit_code"] or not row["originals_preserved"] or
            row["missing_evidence"] != (row["variant"] == "missing-map") for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
