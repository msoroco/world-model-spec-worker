"""Rebind all three independent comparisons to one six-case final-hash probe."""
import copy
import hashlib
import json
from pathlib import Path

from selected_comparison_audit import compare as compare_marked
from absent_reference_comparison import compare as compare_absent
from green_release_comparison import compare as compare_green

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update031-six-case-probe-manifest.json"
INDEX = HERE / "update031-six-case-matrix-index.json"
RUNS = ROOT / ".runtime-work/c110919-update031-six-case-matrix"
SOURCES = ("native_samples.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
           "trace.jsonl", "road_geometry.json", "road.xodr", "overview.mkv",
           "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
PAIRS = (("reference", "contrast", compare_marked),
         ("absent_reference", "absent_reference_contrast", compare_absent),
         ("green_release_wait", "green_release_red_turn", compare_green))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load(suffix, *, diagnostic):
    manifest = read(MANIFEST)
    index = read(INDEX)
    case_id = HERE.name + "__" + suffix
    entry = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
    result = next((row for row in index["results"] if row["case_id"] == case_id and
                   row["candidate_id"] == "primary"), None)
    require(entry is not None and result is not None and
            index["manifest_sha256"] == sha(MANIFEST) and
            entry["kind"] == "delivery" and entry["id"] == "primary" and
            entry["construction_sha256"] == sha(HERE / entry["construction"]),
            "Final-hash comparison case missing or changed")
    proof_path = HERE / result["proof"]
    proof = read(proof_path)
    require(sha(proof_path) == result["sha256"] and
            proof["manifest_sha256"] == sha(MANIFEST) and
            proof["construction_sha256"] == entry["construction_sha256"] and
            proof["original_native_accepted"] is False,
            "Final-hash comparison candidate proof changed")
    run = RUNS / suffix / "primary"
    attempt = run / "compatibility"
    compat_path = attempt / "compatibility.json"
    saved_path = run / "saved/v0001/processing.json"
    compat = read(compat_path)
    saved = read(saved_path)
    require(sha(compat_path) == proof["compatibility_receipt_sha256"] and
            sha(saved_path) == proof["saved_receipt_sha256"] and
            compat["passed"] is True and compat["negative_removed"] == "road_geometry.json" and
            saved["passed"] is True and saved["originals_preserved"] is True and
            saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False,
            "Final-hash comparison source or saved receipt incomplete")
    hashes = {name: sha(attempt / name) for name in SOURCES}
    require(all(saved["original_source_hashes"].get(name) == value
                for name, value in hashes.items()),
            "Final-hash comparison retained source changed")
    samples = rows(attempt / "native_samples.jsonl")
    require(len(samples) == 480 and all(row.get("synthetic_diagnostic") is diagnostic and
            (row.get("speed_provenance") == "synthetic_native_sample") is diagnostic
            for row in samples), "Synthetic source promoted or original source mislabeled")
    return {"case_id": case_id, "config": read(attempt / "config.json"),
            "road": read(attempt / "road_geometry.json"), "samples": samples,
            "frames": rows(attempt / "video_frames.jsonl"),
            "evidence": rows(attempt / "capture/evidence.jsonl"),
            "result": read(attempt / "result.json"), "source_sha256": hashes,
            "saved_processing_sha256": sha(saved_path),
            "construction_sha256": entry["construction_sha256"]}


def main():
    outcomes = []
    negatives = {}
    for left_suffix, right_suffix, compare in PAIRS:
        left = load(left_suffix, diagnostic=True)
        right = load(right_suffix, diagnostic=True)
        outcome = compare(left, right, diagnostic=True)
        require(outcome["source_comparison_passed"] is True and
                outcome["passed"] is False and
                outcome["physical_or_legal_acceptance_claimed"] is False,
                "Diagnostic comparison claimed original acceptance")
        outcomes.append(outcome)
        damaged = copy.deepcopy(right)
        damaged["evidence"][0]["world"]["weather"] = "rain"
        try:
            compare(left, damaged, diagnostic=True)
        except ValueError as error:
            negatives[right_suffix + "__weather_changed"] = str(error)
        else:
            raise AssertionError("Changed comparison weather was accepted")
        try:
            load(left_suffix, diagnostic=False)
        except ValueError as error:
            negatives[left_suffix + "__synthetic_as_original"] = str(error)
        else:
            raise AssertionError("Synthetic source was promoted to original")
    proof = {"format": "c110919-six-case-final-hash-comparison-cpu-proof-v1",
             "manifest_sha256": sha(MANIFEST), "matrix_index_sha256": sha(INDEX),
             "auditor_sha256": {name: sha(HERE / name) for name in
                                ("selected_comparison_audit.py", "absent_reference_comparison.py",
                                 "green_release_comparison.py", "prove-six-case-comparisons.py")},
             "outcomes": outcomes, "negative_rejections": negatives,
             "original_comparisons_accepted": 0, "canonical_selected": False}
    path = HERE / "update031-six-case-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"comparisons_checked": len(outcomes),
                      "negative_rejections": len(negatives),
                      "proof_sha256": sha(path), "canonical_selected": False}))


if __name__ == "__main__":
    main()
