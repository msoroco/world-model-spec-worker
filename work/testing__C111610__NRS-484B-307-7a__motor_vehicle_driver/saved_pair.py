"""Replay sealed original arrow sources for an exact planned comparison pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from comparison_audit import PAIRS, audit
from native_arrow import measure_original
from saved_finalizer import ASSIGNMENT, finalize_saved


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _record(site_path, attempt, suffix, diagnostic):
    site_path, attempt = Path(site_path), Path(attempt)
    site = json.loads(site_path.read_text())
    case_id = ASSIGNMENT + "__" + suffix
    final = finalize_saved(site_path, attempt, case_id, diagnostic=diagnostic)
    receipt = json.loads((attempt / "arrow-event-receipt.json").read_text())
    event_ref = receipt["event_ref"]
    measured = measure_original(site, attempt, event_ref)
    events = json.loads((attempt / event_ref["path"]).read_text())
    sources = {ref["path"]: ref["sha256"] for ref in site["original_sources"]}
    def source(key):
        return sources[site[key]]
    return {
        "case_suffix": suffix,
        "map_sha256": source("map_source_path"),
        "route_source_sha256": source("concurrent_route_source_path" if
            suffix == "arrow_concurrent_movement" else "route_source_path"),
        "crosswalk_source_sha256": source("crosswalk_source_path"),
        "signal_source_sha256": source("signal_source_path"),
        "duration_frames": final["frame_count"],
        "camera_profile_sha256": site["camera_profile_sha256"],
        "official_head_id": site["official_head_id"],
        "ego_approach_id": site["ego_approach_id"],
        "records": measured["records"],
        "concurrent_indications": [row["concurrent_indications"] for row in events],
        "ego_movement": [row["ego_movement"] for row in events],
        "lawful_presence_verdict": final["lawful_presence_verdict"],
        "cautious_entry_verdict": final["cautious_entry_verdict"],
        "right_of_way_verdict": final["right_of_way_verdict"],
        "source_hashes": {"site": _sha(site_path),
                          "aspect": final["original_aspect_sha256"],
                          "events": final["original_event_sha256"]},
    }


def audit_saved_pair(name, left_site, left_attempt, right_site, right_attempt,
                     *, diagnostic=False):
    if name not in PAIRS:
        raise ValueError("unknown exact arrow comparison")
    left_suffix, right_suffix = PAIRS[name][:2]
    left = _record(left_site, left_attempt, left_suffix, diagnostic)
    right = _record(right_site, right_attempt, right_suffix, diagnostic)
    result = audit(name, left, right)
    result["format"] = "c111610-source-bound-arrow-comparison-v1"
    result["case_ids"] = [ASSIGNMENT + "__" + left_suffix,
                          ASSIGNMENT + "__" + right_suffix]
    result["source_hashes"] = {"left": left["source_hashes"],
                               "right": right["source_hashes"]}
    return result
