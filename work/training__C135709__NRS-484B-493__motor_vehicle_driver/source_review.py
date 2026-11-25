"""Bind separately reviewed street and device records to saved Native evidence.

An authored OpenDRIVE signal is a physical proposal. It supplies neither an
official act nor a legal one-way street designation.
"""
import hashlib
import json
from pathlib import Path

REQUIRED = {
    "one-way-designation": ("roadway_is_one_way", "one_way_designation_source_sha256"),
    "street-boundary": ("street_boundary_reviewed", "street_boundary_source_sha256"),
    "device-authority": ("device_official", "device_authority_source_sha256"),
    "device-content": ("notice_prohibits_left_standing_or_parking", "device_content_source_sha256"),
    "device-erection": ("device_erected", "device_erection_source_sha256"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_context(attempt, diagnostic=False):
    """Require each review record and its separate supporting source bytes."""
    attempt = Path(attempt)
    context_path = attempt / "road-context.json"
    if not context_path.is_file():
        raise ValueError("Missing required source: road-context.json")
    context = json.loads(context_path.read_text())
    if context.get("source_kind") != "native_saved_sample":
        raise ValueError("Road context source kind differs")
    if sha(attempt / "road.xodr") != context.get("map_source_sha256"):
        raise ValueError("OpenDRIVE source hash mismatch")
    reviews = {}
    for name, (claim, digest_field) in REQUIRED.items():
        record_path = attempt / "authority-review" / (name + ".json")
        if not record_path.is_file():
            raise ValueError("Missing required source: authority-review/" + name + ".json")
        record = json.loads(record_path.read_text())
        if record.get("assignment_id") != context.get("assignment_id"):
            raise ValueError("Review assignment differs: " + name)
        if record.get("road_id") != context.get("road_id"):
            raise ValueError("Review roadway differs: " + name)
        if record.get("provenance_kind") != ("synthetic_fixture" if diagnostic else "operator_reviewed_original"):
            raise ValueError("Review provenance differs: " + name)
        source = attempt / "authority-review" / (name + ".source.txt")
        if not source.is_file() or sha(source) != record.get("source_sha256"):
            raise ValueError("Missing or changed review source: " + name)
        if not record.get("source_title") or not record.get("source_locator") or not record.get("reviewer"):
            raise ValueError("Incomplete source review: " + name)
        if record.get(claim) is not True:
            raise ValueError("Required activation unverified: " + name)
        context[claim] = True
        context[digest_field] = sha(source)
        reviews[name] = {"record_sha256": sha(record_path), "source_sha256": sha(source)}
    context["reviewed_source_hashes"] = reviews
    return context
