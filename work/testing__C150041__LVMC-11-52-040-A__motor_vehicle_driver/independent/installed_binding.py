"""Bind diagnostic protocol proofs to the current installed CPU receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(kind: str, saved_root: Path) -> dict:
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if (manifest["preparation_status"] != "partial_reviewed_site_and_delivery_pending" or
            manifest["runtime_manifest_sha256"] != sha(REPO / "runtime/SOURCE-MANIFEST.json")):
        raise ValueError("installed manifest is not current and diagnostic")
    case_id = ROOT.name + "__" + kind
    entry = next((item for item in manifest["cases"] if item["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("exact installed case absent")
    construction = ROOT / entry["construction"]
    compatibility = ROOT / entry["compatibility"]["receipt"]
    physical = ROOT / entry["physical_preparation"]["receipt"]
    if (sha(construction) != entry["construction_sha256"] or
            sha(compatibility) != entry["compatibility"]["sha256"] or
            sha(physical) != entry["physical_preparation"]["sha256"]):
        raise ValueError("returned construction or receipt changed")
    compatible = json.loads(compatibility.read_text())
    prepared = json.loads(physical.read_text())
    if (compatible["case_id"] != case_id or compatible["passed"] is not True or
            compatible["construction_sha256"] != entry["construction_sha256"] or
            compatible["runtime_manifest_sha256"] != manifest["runtime_manifest_sha256"] or
            prepared["case_id"] != case_id or
            prepared["construction_sha256"] != entry["construction_sha256"] or
            prepared["physical_acceptance_claimed"] is not False):
        raise ValueError("returned receipts do not select current diagnostic case")
    source = saved_root / kind / "compatibility"
    saved_receipt = saved_root / kind / "saved/v0001/processing.json"
    selection_path = source / "candidate-selection.json"
    selection = json.loads(selection_path.read_text())
    saved = json.loads(saved_receipt.read_text())
    if (selection["case_id"] != case_id or selection["candidate_id"] != "primary" or
            selection["manifest_sha256"] != sha(manifest_path) or
            selection["construction_sha256"] != entry["construction_sha256"] or
            saved["case_id"] != case_id or saved["passed"] is not True or
            saved["recorded_only"] is not True or saved["missing_evidence"] is not False or
            saved["physical_acceptance_claimed"] is not False or
            saved["legal_acceptance_claimed"] is not False):
        raise ValueError("saved attempt does not select current diagnostic manifest")
    return {"case_id": case_id, "source_kind": "synthetic_fixture",
            "original_capture_reviewed": False, "delivery_ready_claimed": False,
            "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
            "execution_manifest_sha256": sha(manifest_path),
            "construction_sha256": entry["construction_sha256"],
            "compatibility_receipt_sha256": sha(compatibility),
            "physical_preparation_receipt_sha256": sha(physical),
            "selection_receipt_sha256": sha(selection_path),
            "saved_receipt_sha256": sha(saved_receipt),
            "source_attempt": str(source)}
