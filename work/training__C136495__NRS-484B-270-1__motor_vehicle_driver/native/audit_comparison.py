"""Independent saved-source isolation audit for the exact bicycle probe pair."""
from __future__ import annotations

import json
from pathlib import Path

from finalize_rider import finalize
from scene import fixed_context


def audit(clear_dir: str | Path, intrusion_dir: str | Path) -> dict:
    folders = [Path(clear_dir), Path(intrusion_dir)]
    manifests = [json.loads((folder / "source-manifest.json").read_text())
                 for folder in folders]
    for manifest, condition in zip(manifests, ("clear", "intrusion")):
        if manifest.get("condition") != condition:
            raise ValueError("Comparison condition or ordering differs")
        if manifest.get("fixed_context") != fixed_context():
            raise ValueError("Comparison fixed context differs")
    if manifests[0]["sha256"] == manifests[1]["sha256"]:
        raise ValueError("Comparison reused the same original source")
    if manifests[0].get("candidate_id") != manifests[1].get("candidate_id"):
        raise ValueError("Comparison candidate engineering differs")
    observed = [finalize(folder) for folder in folders]
    if observed[0]["first_ego_lateral_change_frame"] is not None:
        raise ValueError("Clear control did not preserve the requested ego path")
    if observed[1]["first_ego_lateral_change_frame"] is None:
        raise ValueError("Intrusion control did not realize an ego lateral move")
    if (observed[1]["minimum_lateral_surface_gap_m"] >=
            observed[0]["minimum_lateral_surface_gap_m"]):
        raise ValueError("Original body separation did not vary as requested")
    return {"format": "c136495-independent-comparison-audit-v1",
            "case_ids": [item["case_id"] for item in observed],
            "fixed_context": fixed_context(),
            "deliberate_difference": "original ego lateral path and measured body separation",
            "observed": observed, "physical_acceptance_claimed": False,
            "rider_lawful_status": "unresolved", "driver_intent": "unresolved",
            "causal_interference": "unresolved", "legal_verdict_claimed": False}
