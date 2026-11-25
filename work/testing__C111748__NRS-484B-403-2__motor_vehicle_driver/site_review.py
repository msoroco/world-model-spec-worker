"""Verify reviewed original site records before a production Native run.

This validates provenance and reviewer attestations. It cannot decide that a
traffic-control device is legally official or that its image is legible.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


REQUIRED = {
    "highway": ("highway_status", "source_sha256"),
    "placement_authority": ("device", "authority_source_sha256"),
    "legal_consistency": ("device", "legal_consistency_source_sha256"),
    "display_direction": ("device", "display_source_sha256"),
}


class ReviewError(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(site_path: Path, site_sha256: str, case_id: str,
           review_path: Path, source_root: Path) -> dict:
    """Bind every claimed site source digest to an original reviewed record."""
    site_path = Path(site_path).resolve()
    review_path = Path(review_path).resolve()
    source_root = Path(source_root).resolve()
    if _sha(site_path) != site_sha256:
        raise ReviewError("site source hash mismatch")
    site = json.loads(site_path.read_text())
    review = json.loads(review_path.read_text())
    if site.get("case_id") != case_id or review.get("case_id") != case_id:
        raise ReviewError("review case mismatch")
    if review.get("site_sha256") != site_sha256:
        raise ReviewError("review site hash mismatch")
    if review.get("source_kind") != "original_reviewed_native_site" or review.get("diagnostic_fixture") is not False:
        raise ReviewError("original reviewed site source required")
    if not review.get("reviewer") or not review.get("reviewed_at"):
        raise ReviewError("independent site reviewer missing")
    if not review.get("governed_approach_reviewed") or not review.get("route_envelope_reviewed"):
        raise ReviewError("approach and turn route review missing")
    sources = review.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(REQUIRED):
        raise ReviewError("reviewed authority/display source inventory incomplete")
    verified = {}
    for name, (section, key) in REQUIRED.items():
        source = sources[name]
        if not isinstance(source, dict) or not source.get("path") or not source.get("review_note"):
            raise ReviewError("reviewed source record missing: " + name)
        path = (source_root / source["path"]).resolve()
        if path == source_root or source_root not in path.parents or not path.is_file():
            raise ReviewError("reviewed source path missing or escaped: " + name)
        digest = _sha(path)
        if digest != source.get("sha256") or digest != site.get(section, {}).get(key):
            raise ReviewError("reviewed source hash mismatch: " + name)
        verified[name] = {"path": source["path"], "sha256": digest}
    return {"case_id": case_id, "site_sha256": site_sha256,
            "review_sha256": _sha(review_path), "verified_sources": verified,
            "legal_status": "requires local independent determination",
            "physical_visibility": "requires original pixel review"}
