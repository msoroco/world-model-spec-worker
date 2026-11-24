"""Bind a local Native blueprint probe to an unreviewed red-X source draft.

The output remains pending independent review. Blueprint attribute readback does
not establish the official design, rendered pixels, or the site/lane association.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(draft_path: Path, probe_path: Path, output_path: Path) -> dict:
    draft_path, probe_path, output_path = map(Path, (draft_path, probe_path, output_path))
    if any(path.is_symlink() or not path.is_file() for path in (draft_path, probe_path)):
        raise ValueError("regular draft and probe files required")
    if output_path.exists():
        raise ValueError("probe binding output already exists")
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    if (draft.get("format") != "worker-red-x-source-draft-v1" or
            draft.get("review_status") != "pending_independent_review"):
        raise ValueError("only an unreviewed original-source draft may be bound")
    site = draft.get("site", {})
    required_site = ("route", "travel_direction", "milepost_or_cross_streets",
                     "gantry_or_device_id", "bus_approach", "governed_lane")
    if any(not site.get(key) for key in required_site) or site["governed_lane"] != "red_lane":
        raise ValueError("exact highway site and governed lane missing")
    for key in ("highway", "official_device"):
        item = draft.get(key, {})
        if not isinstance(item, dict) or item.get("reviewer") is not None:
            raise ValueError("original-source draft was altered")
        rel = item.get("source_path")
        if not isinstance(rel, str) or Path(rel).name != rel:
            raise ValueError("original source path must be local")
        source = draft_path.parent / rel
        if source.is_symlink() or not source.is_file() or _sha(source) != item.get("source_sha256"):
            raise ValueError("original source missing or changed")
    if (not isinstance(probe.get("blueprint_id"), str) or
            not probe["blueprint_id"].startswith("static.") or
            probe.get("attribute") != "display_state" or
            probe.get("red_x_value") != "red_x" or
            probe.get("blueprint_readback") is not True or
            probe.get("rendered_pixels_reviewed") is not False or
            probe.get("official_device_design_reviewed") is not False):
        raise ValueError("Native probe lacks an unreviewed red-X blueprint readback")
    binding = {
        "format": "worker-red-x-probe-binding-v1",
        "review_status": "pending_independent_review",
        "source_draft_sha256": _sha(draft_path),
        "highway_source_sha256": draft["highway"]["source_sha256"],
        "official_device_source_sha256": draft["official_device"]["source_sha256"],
        "native_probe_sha256": _sha(probe_path),
        "native_asset_blueprint_id": probe["blueprint_id"],
        "native_display_state": {"attribute": probe["attribute"],
                                 "red_x_value": probe["red_x_value"]},
        "site": site,
        "review_required": ["exact_public_highway_and_site", "official_device_original",
                            "bus_facing_and_governed_lane_join", "rendered_red_x_pixels",
                            "official_design_matches_imported_asset"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return binding


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("probe", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(bind(args.draft, args.probe, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
