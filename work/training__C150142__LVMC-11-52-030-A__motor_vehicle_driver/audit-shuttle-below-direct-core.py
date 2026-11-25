"""Bind the selected shuttle below direct CPU proof to source and decode receipts."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/owner150142/shuttle-below-direct-current"
PROOF = HERE / "current-shuttle-below-primary-direct-core.json"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit():
    proof = read(PROOF)
    manifest = HERE / "execution-manifest.json"
    entry = next(item for item in read(manifest)["cases"]
                 if item["case_id"] == proof["case_id"])
    positive = SCRATCH / "positive"
    negative = SCRATCH / "negative"
    assert proof["passed"] is True
    assert proof["candidate_id"] == "primary"
    assert proof["case_id"] == HERE.name + "__shuttle_bus_below"
    assert proof["frames"] == 36120
    assert proof["manifest_sha256"] == sha(manifest)
    assert proof["construction_sha256"] == entry["construction_sha256"]
    assert proof["positive_analysis_sha256"] == sha(positive / "finalize_selected.py")
    assert read(positive / "candidate-selection.json")["construction_sha256"] == entry["construction_sha256"]
    required = {"acquisition_unchanged", "actual_analysis", "derived_outputs_rebuilt",
                "final_decode", "four_camera_sources", "lean_decoder",
                "mandatory_observations", "native_validation", "render"}
    assert required <= set(proof["core_checks"])
    assert read(positive / "final-decode.json")["frames"] == 36120
    for index in range(4):
        source = read(positive / f"source-{index}.json")
        assert source["passed"] and source["frames"] == 36120
    assert read(positive / "analysis-report.json")["measurements"]["signed_curb_observation"]["value"]["duration_relative_to_30_minutes"] == "below"
    assert proof["measurement_keys"] == ["signed_curb_observation"]
    assert proof["negative_removed"] == "native-passenger-actors.jsonl"
    assert not (negative / proof["negative_removed"]).exists()
    negative_log = SCRATCH / "negative-analysis.log"
    assert sha(negative_log) == proof["negative_log_sha256"]
    assert proof["negative_error_contains"] in negative_log.read_text()
    assert proof["scope"] == "direct synthetic compatibility core; no pinned recipe receipt"
    assert not proof["original_native_observed"]
    assert not proof["physical_acceptance_claimed"]
    assert not proof["legal_acceptance_claimed"]
    return {"format": "c150142-shuttle-below-direct-core-audit-v1", "passed": True,
            "case_id": proof["case_id"], "candidate_id": "primary", "frames": 36120,
            "manifest_sha256": proof["manifest_sha256"], "proof_sha256": sha(PROOF),
            "final_decode_sha256": sha(positive / "final-decode.json"),
            "negative_log_sha256": sha(negative_log),
            "official_recipe_compatibility_passed": False,
            "original_native_observed": False}


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True, indent=2))
