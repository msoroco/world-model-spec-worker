"""Independent source-bound CPU comparison of the two selected turn conditions."""
import argparse
import json
from pathlib import Path

from observed_left_turn import ASSIGNMENT
from saved_measure import analyze


EXPECTED = {
    "a": ASSIGNMENT + "__selected_d457f261__condition_a",
    "b": ASSIGNMENT + "__selected_d457f261__condition_b",
}
COMPARISON = ASSIGNMENT + "__selected_d457f261__comparison"


def audit_reports(reports):
    for suffix, report in zip(("a", "b"), reports):
        if report.get("format") != "c329654-left-turn-saved-measurement-v1" or report.get("case_id") != EXPECTED[suffix]:
            raise ValueError("Exact case or saved analysis identity differs")
        if report.get("source_kind") not in ("original_native", "synthetic_cpu") or report.get("measured", {}).get("source_kind") != report["source_kind"]:
            raise ValueError("Measured source provenance differs")
        if not isinstance(report.get("sources"), dict) or set(report["sources"]) != {
                "config.json", "left-turn-actors.jsonl", "video_frames.jsonl",
                "camera-frames.jsonl", "road.xodr"}:
            raise ValueError("Missing source-bound comparison evidence")
        if any(not isinstance(value, str) or len(value) != 64 for value in report["sources"].values()):
            raise ValueError("Invalid source hash in comparison")
        if report.get("legal_priority_verdict") is not None or report.get("physical_acceptance_claimed") is not False:
            raise ValueError("Comparison cannot assert legal or physical acceptance")
    left, right = reports
    if left["source_kind"] != right["source_kind"]:
        raise ValueError("Compared source kinds differ")
    if left["fixed_conditions"] != right["fixed_conditions"]:
        raise ValueError("Comparison fixed conditions differ")
    if (left.get("requested_turn_policy"), right.get("requested_turn_policy")) != (
            "yield_then_turn", "turn_before_pass"):
        raise ValueError("Comparison deliberate turn policy differs")
    a, b = left["measured"], right["measured"]
    if a.get("frames") != 600 or b.get("frames") != 600 or not all(
            item.get("preturn_wait_observed") is True for item in (a, b)):
        raise ValueError("Full measured yielding sequence absent")
    if a.get("initial_opponent_passed_before_turn") is not True or b.get("initial_opponent_passed_before_turn") is not False:
        raise ValueError("Measured initial-opponent passage contrast differs")
    if not all(item.get("subsequent_opponent_conflict_frame") is not None for item in (a, b)):
        raise ValueError("Subsequent opposing actor history absent")
    if not all(item.get("turn_signal_observed_before_and_at_turn") is True for item in (a, b)):
        raise ValueError("Observed signal before subsequent permission absent")
    if not all(item.get("subsequent_yield_response_observed") is True for item in (a, b)):
        raise ValueError("Measured subsequent opposing response absent")
    return {"format": "c329654-left-turn-comparison-audit-v1",
            "comparison_id": COMPARISON,
            "case_ids": [EXPECTED["a"], EXPECTED["b"]],
            "fixed_conditions_checked": sorted(left["fixed_conditions"]),
            "deliberate_difference": "left_turn_yield_sequence",
            "measured_turn_frames": [a["first_turn_progress_frame"], b["first_turn_progress_frame"]],
            "measured_initial_passage_before_turn": [True, False],
            "preturn_signal_observed": True,
            "subsequent_opposing_response_observed": True,
            "source_kind": left["source_kind"],
            "original_native_comparison_accepted": False,
            "legal_verdict": None}


def audit(analysis_a, analysis_b):
    """Diagnostic report comparison; original source validation uses audit_attempts."""
    return audit_reports([json.loads(Path(path).read_text()) for path in (analysis_a, analysis_b)])


def audit_attempts(attempt_a, attempt_b):
    """Recompute both reports from immutable saved sources before comparing."""
    return audit_reports([analyze(attempt_a), analyze(attempt_b)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-a")
    parser.add_argument("--analysis-b")
    parser.add_argument("--attempt-a")
    parser.add_argument("--attempt-b")
    args = parser.parse_args()
    if (bool(args.attempt_a) != bool(args.attempt_b) or
            bool(args.analysis_a) != bool(args.analysis_b) or
            bool(args.attempt_a) == bool(args.analysis_a)):
        raise SystemExit("Supply one complete saved-attempt or analysis pair")
    result = (audit_attempts(args.attempt_a, args.attempt_b) if args.attempt_a else
              audit(args.analysis_a, args.analysis_b))
    print(json.dumps(result, sort_keys=True))
