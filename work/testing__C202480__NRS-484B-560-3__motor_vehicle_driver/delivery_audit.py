"""Independent consistency audit of one closed crossing delivery attempt.

This validates retained source and decode receipts, not semantic visibility or law.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from geometry_audit import audit as audit_geometry
from native_camera import VIEWS
from owner_release import verify_release
from saved_measurement import analyze
from source_decode import _pinned_auditor, sha


def _document(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("missing delivery document: " + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_decode(video: Path, receipt: Path, count: int,
                   mapping_hash: str, checker_hash: str) -> dict:
    _pinned_auditor()  # Guard the runtime import and its private output root.
    from scenario_pipeline.worker_exchange.media import verify_receipt
    return verify_receipt(video, receipt, count, mapping_sha256=mapping_hash,
                          required_checks={"nonuniform_camera_samples_v1": checker_hash})


def audit(attempt: Path, *, decode_verifier=_verify_decode) -> dict:
    attempt = Path(attempt).resolve()
    if not any(parent.name == ".runtime-work" for parent in attempt.parents):
        raise ValueError("delivery audit requires private original attempt")
    verify_release(attempt)
    expected_report, expected_result = analyze(attempt)
    if (_document(attempt / "analysis-report.json") != expected_report or
            _document(attempt / "result.json") != expected_result):
        raise ValueError("saved analysis differs from original source remeasurement")
    geometry = audit_geometry(attempt)
    if _document(attempt / "geometry-audit.json") != geometry:
        raise ValueError("independent geometry audit receipt differs")
    source_receipt_path = attempt / "source-decode-receipt.json"
    source = _document(source_receipt_path)
    media_path = attempt / "media-receipt.json"
    media = _document(media_path)
    mapping_hash = sha(attempt / "video_frames.jsonl")
    if (source.get("format") != "c202480-four-original-source-decode-v1" or
            source.get("frames") != 900 or
            source.get("frame_map_sha256") != mapping_hash or
            source.get("media_receipt_sha256") != sha(media_path) or
            source.get("sampled_pixels_nonuniform") is not True or
            source.get("feature_visibility_verified") is not False or
            source.get("physical_acceptance_claimed") is not False or
            set(source.get("receipts", {})) != {name for name, _, _ in VIEWS}):
        raise ValueError("four-source decode manifest differs")
    checker_hash = sha(Path(__file__).with_name("source_decode.py"))
    verified = {}
    for name, width, height in VIEWS:
        record = source["receipts"][name]
        path = attempt / ("source-decode-" + name + ".json")
        video = attempt / (name + ".mkv")
        if (record.get("path") != path.name or
                record.get("sha256") != sha(path) or
                media["video_sha256"].get(name) != sha(video)):
            raise ValueError("original source decode or video bytes differ")
        decoded = decode_verifier(video, path, 900, mapping_hash, checker_hash)
        if (decoded.get("dimensions") != [width, height] or
                decoded.get("frames") != 900 or
                decoded.get("video_sha256") != sha(video)):
            raise ValueError("original source decode dimensions or identity differ")
        verified[name] = sha(path)
    return {"format": "c202480-independent-delivery-audit-v1",
            "case_id": expected_result["case_id"],
            "result_sha256": sha(attempt / "result.json"),
            "analysis_report_sha256": sha(attempt / "analysis-report.json"),
            "geometry_audit_sha256": sha(attempt / "geometry-audit.json"),
            "source_decode_receipt_sha256": sha(source_receipt_path),
            "source_decode_receipts_sha256": verified,
            "feature_visibility_verified": False,
            "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt), indent=2))
