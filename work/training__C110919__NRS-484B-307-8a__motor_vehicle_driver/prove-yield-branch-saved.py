"""Bind primary yield comparison to exact diagnostic compatibility and saved receipts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from yield_branch_comparison import compare, load_source, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-yield-branch-execution-manifest.json"
RUNS = ROOT / ".runtime-work/c110919-update034-yield-full-matrix"
NAMES = ("yield_wait", "yield_conflict_entry")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def load(suffix, manifest):
    case_id = HERE.name + "__" + suffix
    entry = next(row for row in manifest["cases"] if row["case_id"] == case_id)
    require(entry["kind"] == "draft_not_selected" and
            entry["construction_sha256"] == sha(HERE / entry["construction"]),
            "Exact primary construction changed")
    run = RUNS / suffix / "primary"
    attempt = run / "compatibility"
    compatibility_path = attempt / "compatibility.json"
    saved_path = run / "saved/v0001/processing.json"
    compatibility = read(compatibility_path)
    saved = read(saved_path)
    require(compatibility["passed"] is True and
            compatibility["case_id"] == case_id and
            compatibility["candidate_id"] == "primary" and
            compatibility["construction_sha256"] == entry["construction_sha256"] and
            compatibility["negative_removed"] == "road_geometry.json" and
            saved["passed"] is True and saved["case_id"] == case_id and
            saved["candidate_id"] == "primary" and
            saved["originals_preserved"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False,
            "Compatibility or saved receipt incomplete")
    names = ("native_samples.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
             "trace.jsonl", "road_geometry.json", "road.xodr", "overview.mkv",
             "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
    source_hashes = {name: sha(attempt / name) for name in names}
    require(all(saved["original_source_hashes"].get(name) == value
                for name, value in source_hashes.items()),
            "Retained source hash differs from saved receipt")
    samples = load_source(attempt / "native_samples.jsonl",
                          source_hashes["native_samples.jsonl"])
    config = read(attempt / "config.json")
    result = read(attempt / "result.json")
    require(result["accepted"] is False and result["legal_verdict_claimed"] is False and
            result["measured_values"]["yield_branch"]["body_pedestrian_overlap_frames"] ==
            [index for index, row in enumerate(samples)
             if row["walker_conflict_occupied"] and
             max(v[0] for v in row["native_body_xy_m"]) >= 8 and
             min(v[0] for v in row["native_body_xy_m"]) <= 12 and
             max(v[1] for v in row["native_body_xy_m"]) >= -4 and
             min(v[1] for v in row["native_body_xy_m"]) <= 4],
            "Saved finalizer overlap differs from retained full body")
    return samples, config, {"case_id": case_id,
                             "construction_sha256": entry["construction_sha256"],
                             "compatibility_sha256": sha(compatibility_path),
                             "saved_processing_sha256": sha(saved_path),
                             "source_sha256": source_hashes}


def reject(call):
    try:
        call()
    except ValueError:
        return True
    raise ValueError("Damaged source was accepted")


def main():
    manifest = read(MANIFEST)
    left, left_config, left_binding = load(NAMES[0], manifest)
    right, right_config, right_binding = load(NAMES[1], manifest)
    identity = {"case_id", "selected_case_id", "supported_case_ids", "case", "case_suffix"}
    require({key: value for key, value in left_config.items() if key not in identity} ==
            {key: value for key, value in right_config.items() if key not in identity},
            "Held capture or controller configuration differs")
    outcome = compare(left, right, diagnostic=True)
    changed_walker = deepcopy(right)
    changed_walker[240]["walker_center_xy_m"] = [10.0, 1.0]
    removed_stop = deepcopy(left)
    for row in removed_stop[100:130]:
        row["speed_mps"] = 1.0
    rejected = {"changed_pedestrian_context": reject(lambda: compare(
                    left, changed_walker, diagnostic=True)),
                "missing_shared_red_stop": reject(lambda: compare(
                    removed_stop, right, diagnostic=True)),
                "synthetic_promoted_as_original": reject(lambda: compare(
                    left, right, diagnostic=False)),
                "wrong_retained_source_hash": reject(lambda: load_source(
                    RUNS / NAMES[0] / "primary/compatibility/native_samples.jsonl",
                    "0" * 64))}
    proof = {"format": "c110919-yield-branch-primary-saved-proof-v1",
             "manifest_sha256": sha(MANIFEST), "comparison": outcome,
             "source_bindings": [left_binding, right_binding],
             "negative_rejections": rejected,
             "canonical_selected": False, "original_native_accepted": False}
    target = HERE / "yield_branch_cases/saved-primary-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"paired_primary_comparison_passed": True,
                      "negative_rejections": sum(rejected.values()),
                      "proof_sha256": sha(target), "canonical_selected": False}))


if __name__ == "__main__":
    main()
