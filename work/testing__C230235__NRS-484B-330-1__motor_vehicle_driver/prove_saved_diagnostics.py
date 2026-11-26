"""Prove all exact synthetic saved stages, independent audits, and comparisons."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

from comparison_audit import audit as audit_comparison
from delivery_audit import audit as audit_delivery
from flagger_zone import CASES
from process_saved import process_saved
from source_packet import ASSIGNMENT


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "tests"))
from test_capture_seal import make_stage


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def prove() -> dict:
    scratch = ROOT / ".runtime-work" / "c230235-saved-diagnostics"
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / "execution-manifest.diagnostic.json").read_text())
    by_case = {item["case_id"]: item for item in manifest["cases"]}
    if set(by_case) != {ASSIGNMENT + "__" + case.name for case in CASES}:
        raise ValueError("manifest case inventory differs")
    stages = {}
    proofs = []
    for case in CASES:
        case_id = ASSIGNMENT + "__" + case.name
        stage = scratch / (case.name + "-original-shaped")
        saved = scratch / (case.name + "-saved")
        for path in (stage, saved):
            if path.exists():
                shutil.rmtree(path)
        stage.mkdir()
        make_stage(stage, case)
        report = process_saved(stage, saved, diagnostic_fixture=True)
        receipt = audit_delivery(stage, saved, case_id=case_id, diagnostic_fixture=True)
        if receipt["source_frames"] != 3 or receipt["physical_acceptance_claimed"]:
            raise ValueError("diagnostic delivery scope differs")
        negative = scratch / (case.name + "-missing-camera")
        if negative.exists():
            shutil.rmtree(negative)
        shutil.copytree(stage, negative)
        (negative / "overview-250.png").unlink()
        try:
            audit_delivery(negative, saved, case_id=case_id, diagnostic_fixture=True)
        except (FileNotFoundError, ValueError):
            pass
        else:
            raise ValueError("missing original camera source was accepted")
        saved_path = HERE / ("diagnostic-saved-" + case.name + ".json")
        delivery_path = HERE / ("diagnostic-delivery-" + case.name + ".json")
        write(saved_path, report)
        write(delivery_path, receipt)
        proofs.append({"case_id": case_id,
                       "construction_sha256": by_case[case_id]["construction_sha256"],
                       "saved_receipt": saved_path.name,
                       "saved_receipt_sha256": sha(saved_path),
                       "delivery_receipt": delivery_path.name,
                       "delivery_receipt_sha256": sha(delivery_path),
                       "missing_original_camera_rejected": True})
        stages[case_id] = {"stage": str(stage), "saved": str(saved)}
    comparisons = audit_comparison(HERE / "case-plan.json", stages, diagnostic_fixture=True)
    comparison_path = HERE / "diagnostic-comparisons.json"
    write(comparison_path, comparisons)
    output = {"format": "c230235-saved-diagnostic-index-v1",
              "assignment_id": ASSIGNMENT,
              "manifest_sha256": sha(HERE / "execution-manifest.diagnostic.json"),
              "plan_sha256": sha(HERE / "case-plan.json"),
              "diagnostic_only": True,
              "case_proofs": proofs,
              "comparison_receipt": comparison_path.name,
              "comparison_receipt_sha256": sha(comparison_path),
              "original_source_acceptance_claimed": False,
              "physical_acceptance_claimed": False,
              "legal_acceptance_claimed": False}
    write(HERE / "saved-diagnostic-index.json", output)
    print(f"{len(CASES)} exact synthetic saved deliveries and {len(comparisons['comparisons'])} comparisons audited")
    return output


if __name__ == "__main__":
    prove()
