"""Rebind five independent comparisons to selected ordinary exact cases."""
import copy
import hashlib
import json
from pathlib import Path

from selected_comparison_audit import compare as compare_marked
from absent_reference_comparison import compare as compare_absent
from green_release_comparison import compare as compare_green
from yield_branch_comparison import compare as compare_yield
from traffic_branch_comparison import compare as compare_traffic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "current-runtime-reproof-manifest.json"
INDEX = HERE / "current-runtime-matrix-progress.json"
RUNS = ROOT / ".runtime-work"
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
    case_id = HERE.name + "__" + suffix
    entry = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
    require(entry is not None and entry["construction_sha256"] == sha(HERE / entry["construction"]),
            "Selected construction changed")
    folder = HERE / "current-runtime-selected-proof" / suffix / "primary"
    compat_path = folder / "compatibility.json"
    saved_path = folder / "saved-processing.json"
    compat, saved = read(compat_path), read(saved_path)
    require(compat["passed"] is True and compat["runtime_manifest_sha256"] ==
            manifest["runtime_manifest_sha256"] and
            compat["construction_sha256"] == entry["construction_sha256"] and
            saved["passed"] is True and saved["originals_preserved"] is True and
            saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False,
            "Current comparison source or saved receipt incomplete")
    attempts = [path for path in (ROOT / ".runtime-work").glob(
        f"c110919-current-{suffix}-primary-*-compat") if
        (path / "compatibility.json").is_file() and
        sha(path / "compatibility.json") == sha(compat_path)]
    require(attempts, "Retained comparison attempt missing")
    attempt = attempts[-1]
    hashes = {name: sha(attempt / name) for name in SOURCES}
    require(all(saved["original_source_hashes"].get(name) == value
                for name, value in hashes.items()),
            "Current comparison retained source changed")
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
    yield_left = load("yield_wait", diagnostic=True)
    yield_right = load("yield_conflict_entry", diagnostic=True)
    yield_outcome = compare_yield(yield_left["samples"], yield_right["samples"],
                                  diagnostic=True)
    require(yield_outcome["source_comparison_passed"] is True and
            yield_outcome["original_delivery_accepted"] is False and
            yield_outcome["legal_verdict_claimed"] is False,
            "Diagnostic pedestrian comparison claimed acceptance")
    outcomes.append(yield_outcome)
    damaged = copy.deepcopy(yield_right["samples"])
    damaged[240]["walker_center_xy_m"] = [10.0, 1.0]
    try:
        compare_yield(yield_left["samples"], damaged, diagnostic=True)
    except ValueError as error:
        negatives["yield_conflict_entry__pedestrian_changed"] = str(error)
    else:
        raise AssertionError("Changed pedestrian source was accepted")
    try:
        compare_yield(yield_left["samples"], yield_right["samples"], diagnostic=False)
    except ValueError as error:
        negatives["yield_wait__synthetic_as_original"] = str(error)
    else:
        raise AssertionError("Synthetic pedestrian source was promoted to original")
    traffic_left = load("traffic_yield_wait", diagnostic=True)
    traffic_right = load("traffic_conflict_entry", diagnostic=True)
    traffic_outcome = compare_traffic(traffic_left["samples"],
                                      traffic_right["samples"], diagnostic=True)
    require(traffic_outcome["source_comparison_passed"] is True and
            traffic_outcome["original_delivery_accepted"] is False and
            traffic_outcome["legal_verdict_claimed"] is False,
            "Diagnostic other-traffic comparison claimed acceptance")
    outcomes.append(traffic_outcome)
    damaged = copy.deepcopy(traffic_right["samples"])
    damaged[240]["other_traffic_signal_state_observed"] = "Red"
    try:
        compare_traffic(traffic_left["samples"], damaged, diagnostic=True)
    except ValueError as error:
        negatives["traffic_conflict_entry__signal_changed"] = str(error)
    else:
        raise AssertionError("Changed other-traffic signal was accepted")
    try:
        compare_traffic(traffic_left["samples"], traffic_right["samples"],
                        diagnostic=False)
    except ValueError as error:
        negatives["traffic_yield_wait__synthetic_as_original"] = str(error)
    else:
        raise AssertionError("Synthetic traffic source was promoted to original")
    proof = {"format": "c110919-selected-ordinary-comparison-cpu-proof-v1",
             "manifest_sha256": sha(MANIFEST), "matrix_index_sha256": sha(INDEX),
             "auditor_sha256": {name: sha(HERE / name) for name in
                                ("selected_comparison_audit.py", "absent_reference_comparison.py",
                                 "green_release_comparison.py", "yield_branch_comparison.py", "traffic_branch_comparison.py",
                                 "prove-current-runtime-ordinary-comparisons.py")},
             "outcomes": outcomes, "negative_rejections": negatives,
             "original_comparisons_accepted": 0, "canonical_selected": True}
    path = HERE / "current-runtime-ordinary-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"comparisons_checked": len(outcomes),
                      "negative_rejections": len(negatives),
                      "proof_sha256": sha(path), "canonical_selected": True}))


if __name__ == "__main__":
    main()
