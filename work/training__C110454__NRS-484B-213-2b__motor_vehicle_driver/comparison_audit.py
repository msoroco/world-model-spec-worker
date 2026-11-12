"""Source-bound selected comparison; fixtures never produce acceptance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from camera_lifecycle_audit import CAMERAS, audit as camera_audit
from saved_comparison_audit import compare_sources
from source_join_audit import read, require, rows, sha

HERE = Path(__file__).resolve().parent
AID = HERE.name
MANIFEST = HERE / "execution-manifest.json"
PAIRS = {"rail": ("rail_reference", "rail_contrast"),
         "rail_at": ("rail_reference", "rail_at"),
         "oneway": ("oneway_absent", "oneway_present"),
         "traversal": ("traversal_reference", "traversal_contrast")}
CHECKS = {"native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"}


def processing_path(saved: Path) -> Path:
    saved = Path(saved).resolve()
    return saved if saved.is_file() else saved / "v0001/processing.json"


def load_side(suffix: str, attempt: Path, saved: Path, *, diagnostic: bool) -> dict:
    attempt, saved = Path(attempt).resolve(), processing_path(saved)
    case = AID + "__" + suffix
    manifest = read(MANIFEST)
    entry = next((item for item in manifest["cases"] if item["case_id"] == case), None)
    require(entry is not None and entry.get("kind") == "delivery", "Unselected comparison case")
    selection = read(attempt / "candidate-selection.json")
    candidate_id = selection.get("candidate_id")
    candidate = entry if candidate_id == "primary" else next(
        (item for item in entry["candidates"] if item["id"] == candidate_id), None)
    require(candidate is not None and
            selection.get("case_id") == case and
            selection.get("manifest_sha256") == sha(MANIFEST) and
            selection.get("construction_sha256") == candidate["construction_sha256"] and
            sha(HERE / candidate["construction"]) == candidate["construction_sha256"],
            "Comparison selection or construction differs")
    camera = camera_audit(attempt, saved, case, candidate_id,
                          candidate["construction_sha256"], diagnostic=diagnostic)
    source_names = ("road_geometry.json", "road.xodr", "statutory_context.json" if
                    suffix.startswith(("rail_", "oneway_")) else "context.json")
    processing = read(saved)
    require(all(processing.get("original_source_hashes", {}).get(name) == sha(attempt / name)
                for name in source_names), "Comparison source hash differs")
    side = {"case_id": case, "candidate_id": candidate_id,
            "attempt": str(attempt), "saved_processing": str(saved),
            "config": read(attempt / "config.json"),
            "road": read(attempt / "road_geometry.json"),
            "samples": rows(attempt / "native_samples.jsonl"),
            "evidence": rows(attempt / "capture/evidence.jsonl"),
            "frames": rows(attempt / "video_frames.jsonl"),
            "road_xodr_sha256": sha(attempt / "road.xodr"),
            "source_sha256": {name: sha(attempt / name) for name in source_names},
            "joined_source_hashes": camera["source_join_sha256"],
            "camera_source_sha256": {name: item["sha256"] for name, item in
                                     camera["camera_sources"].items()},
            "saved_processing_sha256": sha(saved),
            "construction_sha256": candidate["construction_sha256"]}
    if suffix.startswith(("rail_", "oneway_")):
        side["statutory"] = read(attempt / "statutory_context.json")
    else:
        side["context"] = read(attempt / "context.json")
    return side


def check_delivery(side: dict, receipt_path: Path) -> dict:
    receipt_path = Path(receipt_path).resolve()
    receipt = read(receipt_path)
    auditor = (HERE / "delivery_audit.py").resolve()
    local_auditor = next((parent / "state/operations/worker_exchange/full-train-delivery/delivery_audit.py"
                          for parent in HERE.parents if (parent / "batch.json").is_file()), None)
    require(local_auditor is not None and local_auditor.is_file() and
            Path(receipt.get("auditor_path", "")).resolve() == local_auditor.resolve() and
            receipt.get("auditor_sha256") == sha(local_auditor) == sha(auditor) and
            receipt.get("format") == "worker-delivery-audit" and
            receipt.get("passed") is True and
            receipt.get("case_id") == side["case_id"] and
            receipt.get("candidate_id") == side["candidate_id"] and
            receipt.get("source_shaped_unit_test") is not True and
            type(receipt.get("attempt")) is int and receipt["attempt"] >= 1 and
            receipt.get("job_id") and receipt.get("recording_id") and
            receipt.get("frames") == 480 and
            CHECKS <= {key for key, value in receipt.get("checks", {}).items() if value is True} and
            receipt.get("legal_verdict_claimed") is False,
            "Comparison lacks independent original delivery acceptance")
    attempt = Path(side["attempt"])
    video, trace = (attempt / receipt.get(name, "") for name in ("video", "trace"))
    decode_path = Path(receipt.get("source_decode_receipt_path", "")).resolve()
    require(video.is_file() and trace.is_file() and
            attempt in video.resolve().parents and attempt in trace.resolve().parents and
            receipt.get("video_sha256") == sha(video) and
            receipt.get("trace_sha256") == sha(trace) and
            receipt.get("source_result_sha256") == sha(attempt / "result.json") and
            decode_path.is_file() and
            receipt.get("source_decode_receipt_sha256") == sha(decode_path) and
            receipt.get("source_decode_auditor_sha256") == read(decode_path).get("auditor_sha256"),
            "Comparison original result, video, trace or decode receipt differs")
    return {"delivery_receipt_sha256": sha(receipt_path),
            "job_id": receipt["job_id"], "recording_id": receipt["recording_id"],
            "source_result_sha256": receipt["source_result_sha256"],
            "video_sha256": receipt["video_sha256"],
            "trace_sha256": receipt["trace_sha256"]}


def audit(kind: str, left_attempt: Path, left_saved: Path, right_attempt: Path,
          right_saved: Path, *, left_audit: Path | None = None,
          right_audit: Path | None = None, diagnostic: bool = False) -> dict:
    require(kind in PAIRS, "Unknown selected comparison")
    suffixes = PAIRS[kind]
    left = load_side(suffixes[0], left_attempt, left_saved, diagnostic=diagnostic)
    right = load_side(suffixes[1], right_attempt, right_saved, diagnostic=diagnostic)
    plan = read(HERE / "case-plan.json")
    comparison_id = AID + "__comparison_" + kind
    comparison = next((item for item in plan["comparisons"]
                       if item["comparison_id"] == comparison_id), None)
    require(comparison is not None and comparison["case_ids"] ==
            [left["case_id"], right["case_id"]] and
            comparison.get("deliberate_differences"),
            "Declared exact comparison pair differs")
    require(left["candidate_id"] == right["candidate_id"],
            "Paired candidates differ")
    if kind == "traversal":
        require(left["context"] == right["context"],
                "Held traversal context differs")
    observed = compare_sources(kind, left, right)
    accepted = []
    if not diagnostic:
        require(left_audit is not None and right_audit is not None,
                "Comparison needs two original delivery audits")
        accepted = [check_delivery(left, left_audit), check_delivery(right, right_audit)]
    return {"format": "c110454-original-comparison-audit-v1",
            "comparison_id": comparison_id, "case_ids": comparison["case_ids"],
            "declared_differences": comparison["deliberate_differences"],
            "manifest_sha256": sha(MANIFEST),
            "source_bindings": [{key: side[key] for key in
                                 ("case_id", "candidate_id", "source_sha256",
                                  "joined_source_hashes", "camera_source_sha256",
                                  "saved_processing_sha256", "construction_sha256")}
                                for side in (left, right)],
            "delivery_bindings": accepted, **observed,
            "source_comparison_passed": True, "diagnostic_fixture": diagnostic,
            "passed": not diagnostic, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=PAIRS, required=True)
    for arg in ("left-attempt", "left-saved", "right-attempt", "right-saved"):
        parser.add_argument("--" + arg, type=Path, required=True)
    for arg in ("left-audit", "right-audit", "output"):
        parser.add_argument("--" + arg, type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = audit(args.kind, args.left_attempt, args.left_saved,
                   args.right_attempt, args.right_saved,
                   left_audit=args.left_audit, right_audit=args.right_audit,
                   diagnostic=args.diagnostic)
    if args.output:
        require(not args.output.exists(), "Retain previous independent comparison audit")
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
