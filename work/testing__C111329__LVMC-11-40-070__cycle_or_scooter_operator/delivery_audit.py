"""Independent source audit for the bicycle device and officer delivery.

This checker never derives official authority or pixel visibility from an
expected label. Production acceptance additionally needs an original review
packet tied to the exact captured bytes and a separate source decode receipt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_device import read_site
from saved_camera_audit import audit as audit_cameras
from saved_instruction import measure

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case: dict, site_path: Path, site_sha256: str, trace_path: Path,
          trace_sha256: str, *, diagnostic: bool = False,
          review_path: Path | None = None, review_sha256: str | None = None) -> dict:
    site = read_site(Path(site_path), site_sha256)
    if site["device_type"] != case["device_type"]:
        raise ValueError("governing device type differs from selected case")
    trace = Path(trace_path)
    if not diagnostic and json.loads(trace.read_text()).get("diagnostic_fixture") is True:
        raise ValueError("Diagnostic source cannot satisfy delivery audit")
    instruction = measure(trace, trace_sha256, case, site, site_sha256)
    cameras = audit_cameras(trace, trace_sha256, case["case_id"])
    if cameras["decoded_frames"] != instruction["frame_count"]:
        raise ValueError("source frame and camera join differs")
    evidence = {"site": site_sha256, "trace": trace_sha256,
                "cameras": {name: ref["sha256"] for name, ref in
                            json.loads(trace.read_text())["camera_sources"].items()}}
    receipt = {
        "format": "worker-delivery-audit", "case_id": case["case_id"],
        "checks": list(CHECKS), "source_hashes": evidence,
        "instruction_measurement": instruction,
        "source_decode": cameras, "physical_acceptance": False,
        "legal_assessment": "unresolved", "diagnostic_fixture": bool(diagnostic),
    }
    if diagnostic:
        return receipt
    if review_path is None or not review_sha256:
        raise ValueError("Original independent physical and pixel review required")
    if sha(review_path) != review_sha256:
        raise ValueError("original independent review hash mismatch")
    review = json.loads(review_path.read_text())
    if review.get("source_kind") != "original_independent_delivery_review":
        raise ValueError("unverified independent review source")
    if review.get("case_id") != case["case_id"] or review.get("source_hashes") != evidence:
        raise ValueError("independent review source binding differs")
    if review.get("physical_completion") is not True or review.get("actual_pixels") is not True:
        raise ValueError("physical completion or actual pixel review absent")
    if review.get("full_video_decode") is not True or review.get("all_participants") is not True:
        raise ValueError("independent participant or decode review absent")
    receipt["independent_review_sha256"] = review_sha256
    receipt["physical_acceptance"] = True
    return receipt


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--site-sha256", required=True)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--trace-sha256", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--review", type=Path)
    parser.add_argument("--review-sha256")
    args = parser.parse_args()
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    cases = [row for row in plan["cases"] if row["case_id"] == args.case]
    if len(cases) != 1:
        raise ValueError("unknown exact delivery case")
    print(json.dumps(audit(cases[0], args.site, args.site_sha256, args.trace,
                           args.trace_sha256, diagnostic=args.diagnostic,
                           review_path=args.review, review_sha256=args.review_sha256),
                     sort_keys=True))


if __name__ == "__main__":
    main()
