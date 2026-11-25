"""Independent production audit of a saved freight delivery attempt.

The processing receipt and human pixel review must both refer to preserved
original sources. A clean receipt cannot substitute for physical observation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from freight_contract import SourceError
from pixel_review import audit_pixels
from saved_delivery import audit_delivery


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise SourceError(reason)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "delivery artifact is not a JSON object")
    return value


def audit(attempt: Path, processing_path: Path, review_path: Path, *,
          media_probe=None, pixel_decode=None) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    processing_path = Path(processing_path).resolve(strict=True)
    review_path = Path(review_path).resolve(strict=True)
    manifest_path = attempt / "freight-delivery-manifest.json"
    manifest = read(manifest_path)
    require(manifest.get("diagnostic_fixture") is False,
            "diagnostic fixture cannot satisfy independent delivery audit")
    canonical = attempt / "result.json"
    require(canonical.is_file() and sha(canonical) == manifest.get("canonical_result_sha256"),
            "canonical Native result changed")
    processing = read(processing_path)
    case_id = manifest.get("case_id")
    require(processing.get("format") == "worker-saved-processing" and
            processing.get("case_id") == case_id and
            processing.get("passed") is True and
            processing.get("originals_preserved") is True,
            "successful saved-only processing receipt missing")
    preserved = processing.get("original_source_hashes")
    require(isinstance(preserved, dict), "saved original source inventory missing")
    required = {manifest_path.name, "result.json"}
    for section in ("sources", "raw_sources", "media"):
        for ref in manifest.get(section, {}).values():
            path = (attempt / ref["path"]).resolve(strict=True)
            require(path.is_relative_to(attempt), "delivery source escapes original attempt")
            required.add(str(path.relative_to(attempt)))
    require(required <= set(preserved), "processing receipt omitted original sources")
    for relative, digest in preserved.items():
        source = (attempt / relative).resolve(strict=True)
        require(source.is_relative_to(attempt) and source.is_file() and sha(source) == digest,
                "saved original changed: " + relative)
    result_path = Path(processing.get("result", ""))
    require(result_path.is_file() and sha(result_path) == processing.get("result_sha256"),
            "saved processing result changed")
    result = read(result_path)
    require(result.get("case_id") == case_id and
            result.get("diagnostic_fixture") is False,
            "saved result identity or provenance differs")
    delivery = audit_delivery(manifest, attempt_root=attempt,
                              **({"media_probe": media_probe} if media_probe else {}))
    require(delivery["physical_case_completion"] is True and
            delivery["full_video_decode"] is True and
            delivery["all_participants"] is True and delivery["time_join"] is True,
            "physical delivery, participants, time join or full media decode incomplete")
    review = read(review_path)
    pixels = audit_pixels(manifest, attempt=attempt, review=review,
                          **({"decode": pixel_decode} if pixel_decode else {}))
    return {"format": "worker-freight-independent-delivery-audit-v1",
            "case_id": case_id, "passed": True, "source_integrity": True,
            "saved_only_processing": True, "full_video_decode": True,
            "all_participants": True, "time_join": True,
            "actual_pixels_reviewed": pixels["actual_pixels_reviewed"],
            "physical_case_completion": True,
            "processing_sha256": sha(processing_path),
            "pixel_review_sha256": sha(review_path),
            "native_result_sha256": manifest["native_result_sha256"],
            "legal_conclusion": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--processing", required=True, type=Path)
    parser.add_argument("--pixel-review", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.pixel_review),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
