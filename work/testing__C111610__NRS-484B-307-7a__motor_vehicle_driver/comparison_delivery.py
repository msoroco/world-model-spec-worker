"""Replay original arrow histories for one exact diagnostic comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import PAIRS, audit
from native_arrow import measure_original
from saved_finalizer import ASSIGNMENT, finalize_saved


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(attempt, suffix, diagnostic):
    attempt = Path(attempt).resolve()
    site_path = attempt / "site.json"
    site = json.loads(site_path.read_text())
    final = finalize_saved(site_path, attempt, ASSIGNMENT + "__" + suffix,
                           diagnostic=diagnostic)
    event_ref = json.loads((attempt / "arrow-event-receipt.json").read_text())["event_ref"]
    measured = measure_original(site, attempt, event_ref)
    events = json.loads((attempt / event_ref["path"]).read_text())
    sources = {ref["path"]: ref["sha256"] for ref in site["original_sources"]}
    def source(key):
        return sources[site[key]]
    config = json.loads((attempt / "config.json").read_text())
    camera_profile = hashlib.sha256(json.dumps(config["cameras"],
                                                 sort_keys=True).encode()).hexdigest()
    return {"case_suffix": suffix, "map_sha256": source("map_source_path"),
            "route_source_sha256": source("concurrent_route_source_path" if
                                          suffix == "arrow_concurrent_movement" else "route_source_path"),
            "crosswalk_source_sha256": source("crosswalk_source_path"),
            "signal_source_sha256": source("signal_source_path"),
            "duration_frames": final["frame_count"],
            "camera_profile_sha256": site.get("camera_profile_sha256", camera_profile),
            "official_head_id": site["official_head_id"],
            "ego_approach_id": site["ego_approach_id"], "records": measured["records"],
            "concurrent_indications": [row["concurrent_indications"] for row in events],
            "ego_movement": [row["ego_movement"] for row in events],
            "lawful_presence_verdict": final["lawful_presence_verdict"],
            "cautious_entry_verdict": final["cautious_entry_verdict"],
            "right_of_way_verdict": final["right_of_way_verdict"],
            "source_hashes": {"site": sha(site_path),
                              "aspect": final["original_aspect_sha256"],
                              "events": final["original_event_sha256"]}}


def check(name, left, right, diagnostic):
    if name not in PAIRS:
        raise ValueError("unknown exact comparison")
    ls, rs = PAIRS[name][:2]
    l = record(left, ls, diagnostic)
    r = record(right, rs, diagnostic)
    result = audit(name, l, r)
    result.update(format="c111610-source-bound-arrow-comparison-v2",
                  case_ids=[ASSIGNMENT + "__" + ls, ASSIGNMENT + "__" + rs],
                  source_hashes={"left": l["source_hashes"], "right": r["source_hashes"]},
                  diagnostic=diagnostic)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=sorted(PAIRS), required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.comparison, args.left, args.right, args.diagnostic), indent=2))


if __name__ == "__main__":
    main()
