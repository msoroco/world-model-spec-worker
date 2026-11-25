"""Bind saved-only and independent synthetic audits without claiming original capture."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
SCRATCH = REPO / ".runtime-work" / "c135087-saved-v7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(AID + "__")
        source = SCRATCH / suffix / "v0001"
        receipt = json.loads((source / "processing.json").read_text())
        assert receipt["case_id"] == entry["case_id"] and receipt["passed"] is True
        assert receipt["candidate_id"] == "primary" and receipt["originals_preserved"] is True
        assert receipt["timestamp_joins"]["passed"] is True
        assert receipt["missing_evidence"] is False and receipt["final_video_checks"] is not None
        assert receipt["physical_acceptance_claimed"] is False
        assert receipt["legal_acceptance_claimed"] is False
        target = HERE / "proofs" / ("saved-" + suffix)
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / "processing.json", target / "receipt.json")
        shutil.copyfile(source / "analysis.log", target / "analysis.log")
        relative = target.relative_to(HERE)
        entry["saved_processing_diagnostic"] = {
            "receipt": str(relative / "receipt.json"),
            "sha256": sha(target / "receipt.json"),
            "analysis_log": str(relative / "analysis.log"),
            "analysis_log_sha256": sha(target / "analysis.log"),
            "synthetic_only": True,
            "originals_preserved": True}
        positive = HERE / ("audit-" + suffix + "-positive.log")
        negative = HERE / ("audit-" + suffix + "-negative.log")
        assert positive.is_file() and negative.is_file()
        assert "Missing required source: site-original.json" in negative.read_text()
        entry["independent_delivery_diagnostic"] = {
            "script": "audit_delivery_prepared.py",
            "script_sha256": sha(HERE / "audit_delivery_prepared.py"),
            "positive_log": positive.name, "positive_log_sha256": sha(positive),
            "negative_log": negative.name, "negative_log_sha256": sha(negative),
            "synthetic_only": True, "physical_acceptance_claimed": False}
    comparison = HERE / "comparison-audit-receipt.json"
    proof = json.loads(comparison.read_text())
    assert proof["count"] == len(json.loads((HERE / "case-plan.json").read_text())["comparisons"])
    manifest["independent_comparison_diagnostic"] = {
        "receipt": comparison.name, "sha256": sha(comparison), "synthetic_only": True}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print("bound", len(manifest["cases"]), "saved-only and delivery diagnostics;",
          proof["count"], "comparisons")


if __name__ == "__main__":
    bind()
