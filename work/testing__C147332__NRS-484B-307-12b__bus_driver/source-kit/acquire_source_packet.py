"""Stage original local source bytes for a later independent site/device review.

This tool deliberately emits a draft. Generic program material cannot be promoted
to a reviewed site-specific packet by a successful copy or hash check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_SITE = ("route", "travel_direction", "milepost_or_cross_streets",
                 "gantry_or_device_id", "bus_approach", "governed_lane")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stage(manifest_path: Path, output_dir: Path) -> dict:
    """Copy two independently acquired documents with hashes; never assert review."""
    manifest_path, output_dir = Path(manifest_path), Path(output_dir)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("source manifest must be a regular local file")
    spec = json.loads(manifest_path.read_text(encoding="utf-8"))
    site = spec.get("site")
    if not isinstance(site, dict) or any(not site.get(k) for k in REQUIRED_SITE):
        raise ValueError("exact highway site, approach, gantry and lane required")
    if site["governed_lane"] != "red_lane":
        raise ValueError("site governed lane differs from exact scene")
    documents = spec.get("documents")
    if not isinstance(documents, dict) or set(documents) != {"highway", "official_device"}:
        raise ValueError("highway and official-device documents required")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("source output must be empty to avoid replacing retained bytes")
    prepared = {}
    for key in ("highway", "official_device"):
        item = documents[key]
        if not isinstance(item, dict) or not item.get("citation") or not item.get("acquired_from"):
            raise ValueError(key + " original acquisition citation missing")
        source = Path(item.get("local_path", ""))
        if source.is_symlink() or not source.is_file():
            raise ValueError(key + " original local bytes missing or symlinked")
        data = source.read_bytes()
        if not data or len(data) > 2 * 1024 * 1024:
            raise ValueError(key + " original bytes empty or oversized")
        prepared[key] = (data, item)
    output_dir.mkdir(parents=True, exist_ok=True)
    packet = {"format": "worker-red-x-source-draft-v1", "review_status": "pending_independent_review",
              "site": site, "review_required": ["public_highway_at_exact_site",
                    "official_overhead_red_x_at_exact_gantry",
                    "bus_facing_and_governed_lane_join",
                    "native_imported_asset_and_display_state",
                    "source_design_matches_rendered_asset"]}
    for key, (data, item) in prepared.items():
        name = key + ".source"
        (output_dir / name).write_bytes(data)
        packet[key] = {"source_path": name, "source_sha256": _sha(data),
                       "source_citation": item["citation"],
                       "acquired_from": item["acquired_from"],
                       "reviewer": None}
    (output_dir / "draft-context.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    packet = stage(args.manifest, args.output)
    print(json.dumps({"review_status": packet["review_status"],
                      "source_sha256": {k: packet[k]["source_sha256"]
                                        for k in ("highway", "official_device")}}, sort_keys=True))


if __name__ == "__main__":
    main()
