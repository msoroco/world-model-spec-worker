"""Audit the retained long tour-bus direct Core diagnostic."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / ".runtime-work/c150142-1127-tour-bus-below-raw-reuse"
PROOF = HERE / "current-tour-bus-below-primary-direct-core.json"
CASE = HERE.name + "__tour_bus_below"


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
                 if item["case_id"] == CASE)
    assert proof["passed"] is True
    assert proof["case_id"] == CASE and proof["candidate_id"] == "primary"
    assert proof["frames"] == 36120
    assert proof["manifest_sha256"] == sha(manifest)
    assert proof["construction_sha256"] == entry["construction_sha256"]
    assert proof["source_selection_manifest_sha256"] == proof["manifest_sha256"]
    assert proof["source_selection_construction_sha256"] == proof["construction_sha256"]
    assert proof["source_files"] == 36137
    assert proof["negative_removed"] == "native-passenger-actors.jsonl"
    assert proof["negative_error_contains"] == "Missing required source: native-passenger-actors.jsonl"
    assert set(proof["core_checks"]) >= {
        "acquisition_unchanged", "actual_analysis", "derived_outputs_rebuilt",
        "final_decode", "four_camera_sources", "lean_decoder",
        "mandatory_observations", "native_validation", "render"}
    assert proof["official_fixture_recipe_compatibility_passed"] is False
    assert proof["original_native_observed"] is False
    assert proof["physical_acceptance_claimed"] is False
    assert proof["legal_acceptance_claimed"] is False
    positive = OUT / "positive"
    assert read(positive / "candidate-selection.json")["construction_sha256"] == proof["construction_sha256"]
    final = read(positive / "final-decode.json")
    assert final["passed"] is True and final["frames"] == 36120
    for index in range(4):
        source = read(positive / f"source-{index}.json")
        assert source["passed"] is True and source["frames"] == 36120
    log = OUT / "negative-analysis.log"
    assert sha(log) == proof["negative_log_sha256"]
    assert proof["negative_error_contains"] in log.read_text()
    assert not (OUT / "negative" / proof["negative_removed"]).exists()
    return {
        "format": "c150142-retained-long-direct-core-audit-v1",
        "passed": True,
        "case_id": CASE,
        "candidate_id": "primary",
        "frames": 36120,
        "proof_sha256": sha(PROOF),
        "manifest_sha256": proof["manifest_sha256"],
        "construction_sha256": proof["construction_sha256"],
        "final_decode_sha256": sha(positive / "final-decode.json"),
        "source_decode_sha256": [sha(positive / f"source-{i}.json") for i in range(4)],
        "negative_log_sha256": proof["negative_log_sha256"],
        "official_fixture_recipe_compatibility_passed": False,
        "original_native_observed": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
