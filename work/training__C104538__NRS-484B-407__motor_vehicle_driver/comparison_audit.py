"""Independent controlled comparison of the selected 500-foot boundary cases.

Diagnostic evidence checks construction isolation. Completion additionally
requires three independent original-source delivery acceptance receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIXES = ("below_500_ft", "at_500_ft", "above_500_ft")
EXPECTED_LIMITS = (450, 500, 550)
CHECKS = {"native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion"}
FIXED_CONFIG = ("law_id", "cell_id", "actor", "duration_s", "rate_hz",
                "required_atoms", "source_packets", "cameras",
                "recording_description")
SOURCES = ("config.json", "road.xodr", "obstruction.json",
           "native-construction-context.json", "trace.jsonl",
           "capture/evidence.jsonl", "video_frames.jsonl",
           "candidate-selection.json", "acquisition-provenance.json")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def load_case(attempt: Path, saved: Path, case_id: str,
              construction_sha256: str, manifest_sha256: str) -> dict:
    attempt, saved = attempt.resolve(), saved.resolve()
    require(all((attempt/name).is_file() for name in SOURCES),
            "Comparison original source missing")
    hashes = {name: sha(attempt/name) for name in SOURCES}
    config = read(attempt/"config.json")
    selected = read(attempt/"candidate-selection.json")
    obstruction = read(attempt/"obstruction.json")
    context = read(attempt/"native-construction-context.json")
    provenance = read(attempt/"acquisition-provenance.json")
    require(config.get("case_id") == case_id and
            config.get("selected_case_id") == case_id and
            selected.get("case_id") == case_id and
            context.get("case_id") == case_id and
            selected.get("candidate_id") == config.get("candidate_id") ==
                context.get("candidate_id") and
            selected.get("construction_sha256") == construction_sha256 and
            selected.get("manifest_sha256") == manifest_sha256,
            "Comparison selects another case, candidate or construction")
    require(obstruction.get("case_suffix") == case_id.rsplit("__", 1)[-1] and
            obstruction.get("road_xodr_sha256") == hashes["road.xodr"] and
            context.get("authored_road_sha256") == hashes["road.xodr"] and
            context.get("authored_obstruction_sha256") == hashes["obstruction.json"],
            "Comparison road or obstruction source binding differs")
    processing_path = saved/"v0001/processing.json"
    require(processing_path.is_file(), "Comparison saved processing missing")
    processing = read(processing_path)
    require(processing.get("passed") is True and
            processing.get("originals_preserved") is True and
            processing.get("missing_evidence") is False and
            processing.get("case_id") == case_id and
            processing.get("candidate_id") == config["candidate_id"] and
            processing.get("native_revision", {}).get("construction_sha256") ==
                construction_sha256 and
            all(processing.get("original_source_hashes", {}).get(name) == digest
                for name, digest in hashes.items()),
            "Comparison saved processing incomplete")
    return {"case_id": case_id, "attempt": str(attempt), "saved": str(saved),
            "config": config, "obstruction": obstruction, "context": context,
            "provenance": provenance, "processing": processing,
            "source_sha256": hashes, "processing_sha256": sha(processing_path)}


def compare(records: list[dict], plan: dict, *, diagnostic: bool,
            delivery_receipts: list[dict] | None = None) -> dict:
    case_ids = [HERE.name + "__" + suffix for suffix in SUFFIXES]
    require(plan.get("case_ids") == case_ids and
            plan.get("deliberate_differences") ==
                ["opposing_approach_visibility"] and
            len(records) == 3 and
            [record["case_id"] for record in records] == case_ids,
            "Selected comparison identity or declared difference changed")
    configs = [record["config"] for record in records]
    fixed = [{key: config.get(key) for key in FIXED_CONFIG} for config in configs]
    require(all(value == fixed[0] for value in fixed[1:]),
            "Undeclared camera, capture, law or controller difference")
    require(all(config.get("candidate_id") == configs[0].get("candidate_id")
                for config in configs), "Comparison candidates differ")
    roads = [record["source_sha256"]["road.xodr"] for record in records]
    require(len(set(roads)) == 1, "Fixed authored road differs")
    if diagnostic:
        for source in ("trace.jsonl", "capture/evidence.jsonl"):
            require(len({record["source_sha256"][source] for record in records}) == 1,
                    "Diagnostic fixed motion or capture source differs")
    limits = []
    for suffix, record in zip(SUFFIXES, records):
        obstruction = record["obstruction"]
        radius = obstruction.get("inner_radius_m")
        require(type(radius) in (int, float) and 0 < radius < 500,
                "Authored obstruction radius missing")
        derived = 1000*math.acos(radius/500)/.3048
        require(abs(derived-obstruction.get("requested_reference_limit_ft", -1)) < 1e-5 and
                record["config"].get("case_suffix") == suffix,
                "Authored sightline limit differs from geometry")
        limits.append(round(derived))
    require(limits == list(EXPECTED_LIMITS) and len(set(limits)) == 3,
            "Below/at/above 500-foot construction incomplete")
    if diagnostic:
        require(all(record["provenance"].get("diagnostic_fixture") is True and
                    record["provenance"].get("provenance_kind") != "native"
                    for record in records),
                "Diagnostic comparison provenance differs")
        complete = False
    else:
        require(delivery_receipts is not None and len(delivery_receipts) == 3,
                "Comparison needs three original delivery audits")
        from physical_motion_audit import audit as motion_audit
        reviewed_fixed = []
        for record, receipt in zip(records, delivery_receipts):
            auditor = (HERE/"delivery_audit.py").resolve()
            result = Path(record["processing"].get("result", "")).resolve()
            decode = Path(receipt.get("source_decode_receipt_path", "")).resolve()
            review = Path(receipt.get("fixed_condition_review_path", "")).resolve()
            require(record["provenance"].get("provenance_kind") == "native" and
                    record["provenance"].get("diagnostic_fixture") is False and
                    auditor.is_file() and
                    Path(receipt.get("auditor_path", "")).resolve() == auditor and
                    receipt.get("auditor_sha256") == sha(auditor) and
                    receipt.get("format") == "worker-delivery-audit" and
                    receipt.get("case_id") == record["case_id"] and
                    receipt.get("passed") is True and
                    receipt.get("source_shaped_unit_test") is not True and
                    receipt.get("attempt_path") == record["attempt"] and
                    Path(record["saved"]).resolve() in result.parents and
                    result.is_file() and
                    receipt.get("source_result_sha256") == sha(result) and
                    decode.is_file() and
                    receipt.get("source_decode_receipt_sha256") == sha(decode) and
                    review.is_file() and
                    receipt.get("fixed_condition_review_sha256") == sha(review) and
                    CHECKS <= {name for name, passed in
                               receipt.get("checks", {}).items() if passed is True} and
                    receipt.get("legal_verdict_claimed") is False,
                    "Comparison lacks independent original delivery acceptance")
            require(motion_audit(Path(record["attempt"]), record["case_id"])
                    ["native_motion_status"] == "met",
                    "Comparison Native physical reversal absent")
            fixed_review = read(review)
            require(fixed_review.get("format") ==
                        "c104538-original-fixed-condition-review-v1" and
                    fixed_review.get("source_kind") == "original_native_capture" and
                    fixed_review.get("case_id") == record["case_id"] and
                    fixed_review.get("reviewer") and fixed_review.get("method") and
                    fixed_review.get("source_sha256", {}).get("capture/evidence.jsonl") ==
                        record["source_sha256"]["capture/evidence.jsonl"] and
                    fixed_review.get("source_sha256", {}).get("road.xodr") ==
                        record["source_sha256"]["road.xodr"] and
                    set(fixed_review.get("observations", {})) ==
                        set(plan["fixed_conditions"]),
                    "Original fixed-condition review incomplete")
            reviewed_fixed.append(fixed_review["observations"])
        require(all(value == reviewed_fixed[0] for value in reviewed_fixed[1:]),
                "Original fixed conditions differ across selected cases")
        complete = True
    return {"format": "c104538-independent-comparison-audit-v1",
            "comparison_id": plan["comparison_id"], "case_ids": case_ids,
            "candidate_id": configs[0]["candidate_id"],
            "fixed_conditions_checked": list(FIXED_CONFIG) + ["authored road"],
            "declared_difference": "opposing_approach_visibility",
            "authored_center_reference_limits_ft": limits,
            "original_visibility_proven": complete,
            "comparison_complete": complete,
            "source_shaped_unit_test": diagnostic,
            "source_sha256": [record["source_sha256"] for record in records],
            "legal_verdict_claimed": False}


def audit(attempts: list[Path], saved: list[Path], *, diagnostic: bool,
          delivery_receipts: list[dict] | None = None) -> dict:
    require(len(attempts) == len(saved) == 3, "Three selected attempts required")
    manifest_path = HERE/"execution-manifest.json"
    manifest = read(manifest_path)
    plan = read(HERE/"case-plan.json")["comparisons"][0]
    cases = manifest["cases"]
    require([entry["case_id"] for entry in cases] == plan["case_ids"],
            "Selected manifest differs from comparison plan")
    records = [load_case(attempt, output, entry["case_id"],
                         entry["construction_sha256"], sha(manifest_path))
               for attempt, output, entry in zip(attempts, saved, cases)]
    return compare(records, plan, diagnostic=diagnostic,
                   delivery_receipts=delivery_receipts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--saved", type=Path, action="append", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.saved,
                           diagnostic=args.diagnostic), indent=2))
