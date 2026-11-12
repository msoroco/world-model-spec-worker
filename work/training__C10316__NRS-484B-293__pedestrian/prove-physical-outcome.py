"""Retain source-shaped motion branches without promoting synthetic motion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from physical_outcome_audit import audit, classify, read, rows


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(call, expected: str) -> None:
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise
    else:
        raise AssertionError("Expected rejection: " + expected)


def run() -> dict:
    selected = json.loads((HERE / "execution-manifest.json").read_text())
    measured = []
    for entry in selected["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            attempt = ROOT / ".runtime-work" / f"c10316-current-{suffix}-{candidate}-compat"
            result = audit(attempt, case_id, test_shape=True)
            if (result["motion_status"] != "unverified" or
                    result["native_motion_status"] != "unverified" or
                    result["source_shaped_motion_status"] != "met" or
                    result["measured"]["crosswalk_frames"] != 112 or
                    result["physical_acceptance_claimed"] or
                    result["legal_verdict_claimed"]):
                raise AssertionError("Source-shaped motion was promoted or changed")
            measured.append({"case_id": case_id, "candidate_id": candidate,
                             "source_shaped_status": result["source_shaped_motion_status"],
                             "native_motion_status": result["native_motion_status"],
                             "source_sha256": result["source_sha256"]})
    reference = ROOT / ".runtime-work/c10316-current-reference-primary-compat"
    samples = rows(reference / "native_samples.jsonl")
    mapping = rows(reference / "video_frames.jsonl")
    context = read(reference / "crosswalk-context.json")
    wrong_half = classify(samples, mapping, context, "left")
    if wrong_half["status"] != "not_met":
        raise AssertionError("Wrong-half passage was accepted")
    stationary = [{**row, "pedestrian_xy_m": samples[0]["pedestrian_xy_m"],
                   "pedestrian_footprint_xy_m": samples[0]["pedestrian_footprint_xy_m"]}
                  for row in samples]
    no_traversal = classify(stationary, mapping, context, "right")
    if no_traversal["status"] != "not_met" or no_traversal["full_forward_traversal"]:
        raise AssertionError("Stationary source shape was treated as traversal")
    damaged = [dict(row) for row in samples]
    damaged[5] = {**damaged[5], "native_frame": 900}
    rejected(lambda: classify(damaged, mapping, context, "right"),
             "Source frame/time")
    rejected(lambda: audit(reference, HERE.name + "__reference"),
             "Synthetic or unsealed")
    with tempfile.TemporaryDirectory() as directory:
        missing = audit(Path(directory), HERE.name + "__reference", test_shape=True)
    if (missing["motion_status"] != "unverified" or
            "native_samples.jsonl" not in missing["missing_sources"]):
        raise AssertionError("Missing evidence was promoted")
    proof = {"format": "c10316-physical-outcome-cpu-proof-v1",
             "script_sha256": sha(HERE / "physical_outcome_audit.py"),
             "selected_manifest_sha256": sha(HERE / "execution-manifest.json"),
             "source_shaped_attempts": measured,
             "wrong_half_status": wrong_half["status"],
             "stationary_status": no_traversal["status"],
             "changed_frame_rejected": True,
             "synthetic_production_rejected": True,
             "missing_evidence_status": missing["motion_status"],
             "original_native_motion_proven": False,
             "physical_or_legal_acceptance": False}
    path = HERE / "update018-physical-outcome-cpu-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"source_shaped_attempts": len(measured),
                      "wrong_half_status": wrong_half["status"],
                      "stationary_status": no_traversal["status"],
                      "missing_evidence_status": missing["motion_status"],
                      "original_native_motion_proven": False,
                      "proof_sha256": sha(path)}))
    return proof


if __name__ == "__main__":
    run()
