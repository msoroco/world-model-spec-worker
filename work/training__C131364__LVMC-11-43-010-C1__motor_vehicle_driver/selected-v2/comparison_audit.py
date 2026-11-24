"""Independent original-attempt comparison, after each case's physical review.

CPU fixtures exercise isolation and altered-source rejection only. They make no
claim that a Native attempt has run or that a lane choice is legally correct.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "selected-v2"))
from delivery_audit import original_attempt  # noqa: E402


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compare(left, right, left_review, right_review):
    require(left["case_id"] != right["case_id"], "Comparison requires distinct exact cases")
    require(left_review["case_id"] == left["case_id"] and
            right_review["case_id"] == right["case_id"],
            "Physical review case identity differs")
    for key in ("road_sha256", "duration_s", "rate_hz", "cameras", "actor",
                "cell_id", "law_id", "required_atoms", "source_packets"):
        require(left.get(key) == right.get(key), "Comparison fixed condition differs: " + key)
    require(left_review.get("observed_circulating_lane") == -1 and
            right_review.get("observed_circulating_lane") == -2,
            "Original circulating lane contrast unverified")
    require(left_review["physical_completion"] is True and
            right_review["physical_completion"] is True,
            "Both original passages require independent physical review")
    require(left_review["sealed_original_sha256"] != right_review["sealed_original_sha256"],
            "Comparison reuses one original recording")
    return {"comparison_variable": "roundabout_exit_lane", "fixed_conditions_verified": True,
            "distinct_originals": True, "legal_verdict": None}


def cpu_test(mode):
    base = {"road_sha256": "r" * 64, "duration_s": 30, "rate_hz": 20,
            "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
            "actor": "motor_vehicle_driver", "cell_id": "C131364",
            "law_id": "LVMC-11-43-010-C1", "required_atoms": [], "source_packets": []}
    left = {**base, "case_id": ROOT.name + "__witness_1"}
    right = {**base, "case_id": ROOT.name + "__witness_2"}
    first = {"case_id": left["case_id"], "physical_completion": True,
             "sealed_original_sha256": "a" * 64, "observed_circulating_lane": -1}
    second = {"case_id": right["case_id"], "physical_completion": True,
              "sealed_original_sha256": "b" * 64, "observed_circulating_lane": -2}
    if mode == "negative":
        right["road_sha256"] = "tampered-road"
    return {"format": "c131364-comparison-cpu-selftest", **compare(left, right, first, second),
            "fixture_only": True, "physical_acceptance_claimed": False}


def actual(args):
    manifest = json.loads((ROOT / "selected-v2-manifest.json").read_text())
    cases = manifest["cases"]
    require(len(cases) == 2, "Exact two-case selected comparison required")
    reports = [original_attempt(case["case_id"], attempt, review) for case, attempt, review in
               zip(cases, (args.attempt1, args.attempt2), (args.review1, args.review2))]
    configs = [json.loads((Path(path) / "config.json").read_text()) for path in
               (args.attempt1, args.attempt2)]
    reviews = [json.loads(Path(path).read_text()) for path in (args.review1, args.review2)]
    for index, attempt in enumerate((args.attempt1, args.attempt2), 1):
        history = [json.loads(line) for line in
                   (Path(attempt) / "native-raw-actors.jsonl").read_text().splitlines()]
        circulating = [row["observed_lane_id"] for row in history
                       if row["observed_road_id"] == 11]
        require(len(circulating) >= 20 and set(circulating) == {-index},
                "Original circulating lane history differs from selected pair")
    enriched = [{**report, "observed_circulating_lane": review.get("observed_circulating_lane")}
                for report, review in zip(reports, reviews)]
    result = compare(*configs, *enriched)
    return {"format": "worker-comparison-audit", "comparison_id": manifest["comparisons"][0]["comparison_id"],
            "case_ids": [case["case_id"] for case in cases], **result,
            "original_seal_sha256": [report["sealed_original_sha256"] for report in reports],
            "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "physical_acceptance_claimed": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu-test", choices=("positive", "negative"))
    parser.add_argument("--attempt1")
    parser.add_argument("--attempt2")
    parser.add_argument("--review1")
    parser.add_argument("--review2")
    args = parser.parse_args()
    if args.cpu_test:
        print(json.dumps(cpu_test(args.cpu_test)))
    else:
        require(all((args.attempt1, args.attempt2, args.review1, args.review2)),
                "Both original attempts and physical reviews required")
        print(json.dumps(actual(args)))
