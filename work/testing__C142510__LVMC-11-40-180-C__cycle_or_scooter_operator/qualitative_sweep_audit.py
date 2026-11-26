"""Source-bound engineering sweep review for sidewalk overtaking.

The review records observations and independent human impressions. It does not
decide right of way, legal audibility, or compliance with LVMC 11.40.180(C).
"""
import argparse
import hashlib
import json
from pathlib import Path

from sidewalk_overtake import ASSIGNMENT, SOURCES

HERE = Path(__file__).resolve().parent
REQUIRED_SOURCES = set(SOURCES)
KINDS = {"yielding", "audible_signal"}
LABELS = {
    "yielding": {"observed_pause_or_brake", "observed_advance", "indeterminate"},
    "audible_signal": {"heard_at_pedestrian", "not_heard_at_pedestrian", "indeterminate"},
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def audit(case_id, receipt_path, review_path, sweep_id):
    plan = read(HERE / "case-plan.json")
    selected = {row["case_id"]: row for row in plan["cases"]}
    require(case_id in selected and case_id.startswith(ASSIGNMENT + "__"),
            "exact selected case required")
    specs = {row["sweep_id"]: row for row in plan["judgment_range_inventory"]}
    require(sweep_id in specs, "unknown engineering sweep")
    spec = specs[sweep_id]
    kind = spec["kind"]
    require(kind in KINDS and case_id in spec["case_ids"],
            "case not assigned to engineering sweep")
    receipt = read(receipt_path)
    require(receipt.get("format") == "c142510-independent-original-audit-v1" and
            receipt.get("case_id") == case_id and
            receipt.get("source_kind") == "original_native_capture" and
            receipt.get("physical_acceptance") is False and
            receipt.get("legal_status") == "unresolved", "original independent receipt required")
    source = receipt.get("source_sha256")
    require(isinstance(source, dict) and REQUIRED_SOURCES <= set(source) and
            all(isinstance(source[name], str) and len(source[name]) == 64 for name in SOURCES) and
            source == receipt.get("measurement", {}).get("source_sha256"),
            "original source hashes incomplete or changed")
    site = receipt.get("fixed_site", {})
    require(site.get("sidewalk_id") and site.get("sidewalk_polygon_xy_m") and
            site.get("map_sha256") == source["road.xodr"] and
            site.get("sidewalk_map_sha256") == source["road.xodr"],
            "reviewed connected sidewalk source required")
    measured = receipt["measurement"]
    require(measured.get("frame_count") == 900 and
            measured.get("case_id") == case_id and
            measured.get("legal_verdict_claimed") is False and
            isinstance(measured.get("pass_bracket_s"), list) and
            len(measured["pass_bracket_s"]) == 2,
            "original 900-frame passing measurement required")
    review = read(review_path)
    require(review.get("case_id") == case_id and review.get("sweep_id") == sweep_id and
            review.get("kind") == kind and review.get("source_receipt_sha256") == digest(receipt_path) and
            review.get("source_sha256") == source and
            review.get("source_manifest_sha256") == receipt.get("source_manifest_sha256"),
            "independent review source binding missing")
    require(review.get("reviewer") and review.get("method") and
            review.get("independent_of_capture") is True and
            review.get("qualitative_observation") in LABELS[kind] and
            review.get("legal_verdict") is None,
            "independent qualitative observation without legal verdict required")
    intervals = review.get("original_intervals_s")
    require(isinstance(intervals, list) and intervals and
            all(isinstance(v, list) and len(v) == 2 and
                all(type(t) in (int, float) for t in v) and
                v[0] <= measured["pass_bracket_s"][0] <= measured["pass_bracket_s"][1] <= v[1]
                for v in intervals), "original passing interval missing")
    if kind == "audible_signal":
        require(review.get("pedestrian_listening_position_source") and
                review.get("emitter_capability_source") and
                review.get("microphone_capability_source") and
                isinstance(measured.get("original_emitter_event_times_s"), list) and
                isinstance(measured.get("microphone"), dict),
                "original emitter, pedestrian listening, and microphone evidence required")
    else:
        require(review.get("pedestrian_precedence_source") and
                review.get("pedestrian_response_source") and
                isinstance(measured.get("brake_frames_before_pass"), list),
                "original pedestrian precedence and response evidence required")
    return {"format": "c142510-source-bound-qualitative-sweep-v1",
            "case_id": case_id, "sweep_id": sweep_id, "kind": kind,
            "source_receipt_sha256": digest(receipt_path),
            "review_sha256": digest(review_path),
            "qualitative_observation": review["qualitative_observation"],
            "legal_verdict": None, "physical_acceptance": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--sweep-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "retain prior sweep report")
    args.output.write_text(json.dumps(audit(args.case_id, args.receipt, args.review,
                                            args.sweep_id), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
