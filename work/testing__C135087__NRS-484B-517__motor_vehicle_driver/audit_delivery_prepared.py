"""Independent selected saved-source delivery audit; diagnostics remain synthetic."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from stand_delivery import audit as audit_saved_delivery


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case_id, attempt_path, manifest_path, negative_missing_source=False):
    root = Path(attempt_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    entry = next((item for item in manifest["cases"] if item["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("selected case absent from manifest")
    if sha(manifest_path.parent / entry["construction"]) != entry["construction_sha256"]:
        raise ValueError("selected construction changed")
    if negative_missing_source:
        scratch = manifest_path.parents[2] / ".runtime-work"
        with tempfile.TemporaryDirectory(dir=scratch, prefix="c135087-missing-site-") as temporary:
            negative = Path(temporary)
            for name in ("analysis.py", "stand.py", "stand_delivery.py", "stand_media_audit.py",
                         "config.json", "attempt-source.json"):
                shutil.copy2(root / name, negative / name)
            command = [sys.executable, str(negative / "analysis.py"), "--attempt", str(negative),
                       "--output", str(negative / "analysis-report.json")]
            result = subprocess.run(command, text=True, capture_output=True, timeout=30)
            expected = "Missing required source: site-original.json"
            if result.returncode == 0 or expected not in result.stdout + result.stderr:
                raise ValueError("missing original-site negative failed to reject as specified")
            raise ValueError(expected + " (selected finalizer rejected an actually removed source)")
    for name in ("site-original.json", "vehicle-original.json", "attempt-source.json",
                 "actor-rows.json", "frame-map.json"):
        if not (root / name).is_file() or (root / name).is_symlink():
            raise ValueError("Missing required source: " + name)
    provenance = json.loads((root / "acquisition-provenance.json").read_text())
    if provenance.get("provenance_kind") != "synthetic_fixture" or provenance.get("diagnostic_fixture") is not True:
        raise ValueError("this CPU audit accepts only clearly marked diagnostic input")
    attempt = json.loads((root / "attempt-source.json").read_text())
    if attempt["case_id"] != case_id:
        raise ValueError("selected saved case differs")
    source = audit_saved_delivery(root)
    report = json.loads((root / "analysis-report.json").read_text())
    if report.get("case_id") != case_id or report.get("diagnostic_fixture") is not True:
        raise ValueError("selected analysis report missing or claims non-diagnostic provenance")
    seals = next(iter(report["measurements"].values()))["sources"]
    for name in ("site-original.json", "vehicle-original.json", "attempt-source.json"):
        if seals[name] != sha(root / name):
            raise ValueError("selected measurement source differs: " + name)
    if source["original_frame_count"] != 900 or source["decoded_camera_frames"] != 3600:
        raise ValueError("full selected delivery source is incomplete")
    return {"format": "c135087-selected-saved-delivery-audit", "case_id": case_id,
            "construction_sha256": entry["construction_sha256"],
            "attempt_source_sha256": sha(root / "attempt-source.json"),
            "analysis_report_sha256": sha(root / "analysis-report.json"),
            "original_frame_count": 900, "decoded_camera_frames": 3600,
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
            "pixel_visibility_claimed": False, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--negative-missing-source", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.manifest,
                           args.negative_missing_source), indent=2))


if __name__ == "__main__":
    main()
