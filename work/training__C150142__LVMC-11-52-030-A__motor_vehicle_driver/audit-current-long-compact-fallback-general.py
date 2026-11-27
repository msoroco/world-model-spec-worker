"""Audit a selected full-duration fallback's source and candidate bindings."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = (REPO / ".runtime-work").resolve()
REQUIRED = {"acquisition_unchanged", "actual_analysis", "derived_outputs_rebuilt",
            "final_decode", "four_camera_sources", "lean_decoder",
            "mandatory_observations", "native_validation", "render"}
SOURCES = ("acquisition-provenance.json", "native-passenger-actors.jsonl",
           "native-raw-actors.jsonl", "video_frames.jsonl", "overview.mkv",
           "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(proof_path: Path, output: Path, fixture: Path) -> dict:
    proof_path, output, fixture = (path.resolve() for path in (proof_path, output, fixture))
    if proof_path.parent != ROOT or SCRATCH not in output.parents or SCRATCH not in fixture.parents:
        raise ValueError("Audit paths differ from returned proof or ignored scratch")
    proof = load(proof_path)
    candidate_id = proof.get("candidate_id")
    if candidate_id not in {"fallback1", "fallback2", "fallback3"}:
        raise ValueError("Expected a selected fallback")
    manifest = ROOT / "execution-manifest.json"
    entry = next(item for item in load(manifest)["cases"] if item["case_id"] == proof["case_id"])
    candidate = next(item for item in entry["candidates"] if item["id"] == candidate_id)
    if not (proof.get("passed") is True
            and proof.get("manifest_sha256") == sha(manifest)
            and proof.get("construction_sha256") == candidate["construction_sha256"]
            and REQUIRED <= set(proof.get("core_checks", []))
            and proof.get("measurement_keys") == ["signed_curb_observation"]
            and proof.get("official_fixture_recipe_compatibility_passed") is False
            and proof.get("original_native_observed") is False
            and proof.get("physical_acceptance_claimed") is False
            and proof.get("legal_acceptance_claimed") is False):
        raise ValueError("Selected fallback proof binding differs")
    positive, negative = output / "positive", output / "negative"
    selected = load(positive / "candidate-selection.json")
    if selected["candidate_id"] != candidate_id or selected["construction_sha256"] != candidate["construction_sha256"]:
        raise ValueError("Positive package selected another candidate")
    final = load(positive / "final-decode.json")
    if final["passed"] is not True or final["frames"] != 36120:
        raise ValueError("Full selected final decode missing")
    for index in range(4):
        source = load(positive / f"source-{index}.json")
        if source["passed"] is not True or source["frames"] != 36120:
            raise ValueError("Full source decode missing")
    for source in SOURCES:
        if sha(fixture / source) != sha(positive / source):
            raise ValueError("Original synthetic source changed: " + source)
    removed = proof["negative_removed"]
    negative_log = output / "negative-analysis.log"
    if removed != "native-passenger-actors.jsonl" or (negative / removed).exists():
        raise ValueError("Missing-source negative did not remove required input")
    if sha(negative_log) != proof["negative_log_sha256"] or proof["negative_error_contains"] not in negative_log.read_text():
        raise ValueError("Missing-source negative did not reject")
    return {"format": "c150142-compact-full-long-fallback-audit-v2", "passed": True,
            "case_id": proof["case_id"], "candidate_id": candidate_id, "frames": 36120,
            "proof_sha256": sha(proof_path), "manifest_sha256": sha(manifest),
            "construction_sha256": candidate["construction_sha256"],
            "final_decode_sha256": sha(positive / "final-decode.json"),
            "negative_log_sha256": sha(negative_log),
            "official_fixture_recipe_compatibility_passed": False,
            "original_native_observed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.proof, args.output, args.fixture), indent=2, sort_keys=True))
