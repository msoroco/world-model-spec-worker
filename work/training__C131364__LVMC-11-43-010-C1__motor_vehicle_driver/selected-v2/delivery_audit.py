"""Independent original-source delivery checker for the selected left-turn pair.

CPU self-tests exercise the decision boundary. They never represent a real
CARLA recording, actual pixel review, or statutory conclusion.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CASE_IDS = tuple(f"{ROOT.name}__witness_{index}" for index in (1, 2))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def evaluate(case_id, source, review):
    require(case_id in CASE_IDS and source.get("case_id") == case_id and review.get("case_id") == case_id,
            "Exact selected case identity differs")
    require(source.get("source_verified") is True and source.get("frames") == 600 and source.get("camera_count") == 4,
            "Complete sealed Native source required")
    require(review.get("sealed_original_sha256") == source.get("sealed_original_sha256"),
            "Physical review references another Native seal")
    for name in CAMERAS:
        require(review.get("camera_sha256", {}).get(name) == source.get("camera_sha256", {}).get(name),
                "Physical review references another original camera: " + name)
    for field in ("all_participants_reviewed", "time_join_reviewed", "full_video_decode_reviewed",
                  "actual_pixels_reviewed", "physical_roundabout_verified", "left_turn_exit_observed",
                  "left_lane_adjacency_reviewed", "lane_history_reviewed", "physical_completion_reviewed"):
        require(review.get(field) is True, "Independent physical review incomplete: " + field)
    require(review.get("legal_verdict") is None, "Delivery review cannot assign a legal verdict")
    return {"case_id": case_id, "checks": ["native_source", "all_participants", "time_join",
            "full_video_decode", "actual_pixels", "physical_completion"],
            "sealed_original_sha256": source["sealed_original_sha256"],
            "physical_completion": True, "legal_verdict": None}


def cpu_test(case_id, mode):
    source = {"case_id": case_id, "source_verified": True, "frames": 600, "camera_count": 4,
              "sealed_original_sha256": "a" * 64, "camera_sha256": {name: name + "-fixture" for name in CAMERAS}}
    review = {"case_id": case_id, "sealed_original_sha256": "a" * 64,
              "camera_sha256": dict(source["camera_sha256"]), "legal_verdict": None}
    for field in ("all_participants_reviewed", "time_join_reviewed", "full_video_decode_reviewed",
                  "actual_pixels_reviewed", "physical_roundabout_verified", "left_turn_exit_observed",
                  "left_lane_adjacency_reviewed", "lane_history_reviewed", "physical_completion_reviewed"):
        review[field] = True
    if mode == "negative":
        review["camera_sha256"]["driver_reference"] = "tampered-fixture"
    result = evaluate(case_id, source, review)
    return {"format": "c131364-delivery-audit-cpu-selftest", "case_id": case_id,
            "checker_logic_passed": bool(result), "physical_acceptance_claimed": False,
            "fixture_only": True}


def original_attempt(case_id, attempt, review_path):
    require(review_path is not None, "Independent physical review receipt required")
    script = ROOT / "native/v2_source_audit.py"
    spec = importlib.util.spec_from_file_location("c131364_native_source_audit", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = module.audit(attempt)
    require(source["case_id"] == case_id, "Exact selected case identity differs")
    seal = json.loads((Path(attempt) / "capture-seal.json").read_text())
    source["camera_sha256"] = {name: seal["sources"][name + ".mkv"] for name in CAMERAS}
    raw = module.rows(Path(attempt) / "native-raw-actors.jsonl")
    road = [row.get("observed_road_id") for row in raw]
    lane = [row.get("observed_lane_id") for row in raw]
    require(all(value is not None for value in road + lane), "Original road/lane history incomplete")
    require(10 in road and 11 in road and 12 in road and
            road.index(10) < road.index(11) < road.index(12),
            "Original entry-circulation-exit route incomplete")
    review = json.loads(Path(review_path).read_text())
    result = evaluate(case_id, source, review)
    return {"format": "worker-delivery-audit", **result,
            "auditor_path": str(Path(__file__).resolve()), "auditor_sha256": sha(Path(__file__)),
            "source_auditor_sha256": sha(script), "physical_acceptance_claimed": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt")
    parser.add_argument("--review")
    parser.add_argument("--cpu-test", choices=("positive", "negative"))
    args = parser.parse_args()
    if args.cpu_test:
        print(json.dumps(cpu_test(args.case, args.cpu_test)))
    else:
        require(args.attempt is not None, "Original Native attempt required")
        print(json.dumps(original_attempt(args.case, args.attempt, args.review)))
