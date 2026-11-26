"""Validate source bindings for an intended restricted parking site.

The records are supplied by local original-source review. Successful parsing
establishes integrity and identity only, not official status or legal character.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking_place import ASSIGNMENT, _polygon


SOURCE_KINDS = ("map", "device", "authority", "extent", "place_facts")


def reviewed_site(path: str | Path, case_id: str) -> dict:
    path = Path(path).resolve()
    site = json.loads(path.read_text(encoding="utf-8"))
    if site.get("assignment_id") != ASSIGNMENT or site.get("case_id") != case_id:
        raise ValueError("exact assignment and case site required")
    if site.get("review_status") != "reviewed_original_source":
        raise ValueError("independent original source review required")
    for field in ("map_id", "device_id", "designated_place_id", "device_instructions"):
        if not site.get(field):
            raise ValueError("missing site identity or instructions: " + field)
    if site.get("device_erected") is not True:
        raise ValueError("erected device source required")
    if site.get("place_context_for_review") not in ("hazardous", "congested"):
        raise ValueError("hazardous or congested place facts required")
    _polygon(site.get("designated_place_polygon"))
    sources = site.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_KINDS):
        raise ValueError("all five original source bindings required")
    checked = {}
    for kind in SOURCE_KINDS:
        binding = sources[kind]
        if not isinstance(binding, dict) or binding.get("origin") != "reviewed_original":
            raise ValueError("reviewed original source required: " + kind)
        relative = binding.get("path")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError("relative source path required: " + kind)
        unresolved = path.parent / relative
        source = unresolved.resolve()
        if (unresolved.is_symlink() or not source.is_relative_to(path.parent)
                or not source.is_file()):
            raise ValueError("original source missing or escapes site directory: " + kind)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != binding.get("sha256"):
            raise ValueError("original source hash differs: " + kind)
        record = json.loads(source.read_text(encoding="utf-8"))
        if record.get("source_kind") != kind or record.get("map_id") != site["map_id"]:
            raise ValueError("source kind or map identity differs: " + kind)
        if kind != "map" and record.get("device_id") != site["device_id"]:
            raise ValueError("device source identity differs: " + kind)
        if kind in ("extent", "place_facts") and record.get("designated_place_id") != site["designated_place_id"]:
            raise ValueError("designated place identity differs: " + kind)
        checked[kind] = {"path": str(source), "sha256": digest}
    device = json.loads(Path(checked["device"]["path"]).read_text(encoding="utf-8"))
    extent = json.loads(Path(checked["extent"]["path"]).read_text(encoding="utf-8"))
    place = json.loads(Path(checked["place_facts"]["path"]).read_text(encoding="utf-8"))
    if device.get("erected") is not True or device.get("instructions") != site["device_instructions"]:
        raise ValueError("erected device or instructions differ")
    if extent.get("polygon") != site["designated_place_polygon"]:
        raise ValueError("governed extent differs")
    if place.get("context_for_review") != site["place_context_for_review"]:
        raise ValueError("place facts differ")
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "site_path": str(path), "site_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_bindings": checked,
            "review_limit": "Hash and identity checks do not decide official authority, place character or actual CARLA applicability."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(reviewed_site(args.site, args.case), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
