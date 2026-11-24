"""Assemble a reviewed packet only from retained originals and an independent review.

The reviewer supplies findings; this tool checks custody and required joins. It
cannot decide whether the source or design is genuinely official.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(draft_path: Path, probe_path: Path, binding_path: Path,
             review_path: Path, output_path: Path) -> dict:
    draft_path, probe_path, binding_path, review_path, output_path = map(
        Path, (draft_path, probe_path, binding_path, review_path, output_path))
    if output_path.exists():
        raise ValueError("reviewed packet output already exists")
    if output_path.parent.resolve() != draft_path.parent.resolve():
        raise ValueError("reviewed packet must stay beside retained originals")
    inputs = (draft_path, probe_path, binding_path, review_path)
    if any(path.is_symlink() or not path.is_file() for path in inputs):
        raise ValueError("regular draft, probe, binding and review files required")
    draft, probe, binding, review = [json.loads(path.read_text(encoding="utf-8"))
                                     for path in inputs]
    if draft.get("format") != "worker-red-x-source-draft-v1" or draft.get("review_status") != "pending_independent_review":
        raise ValueError("original-source draft is not pending")
    if binding.get("format") != "worker-red-x-probe-binding-v1" or binding.get("review_status") != "pending_independent_review":
        raise ValueError("probe binding is not pending")
    for key, expected in (("source_draft_sha256", _sha(draft_path)),
                          ("native_probe_sha256", _sha(probe_path)),
                          ("site", draft.get("site")),
                          ("native_asset_blueprint_id", probe.get("blueprint_id"))):
        if binding.get(key) != expected:
            raise ValueError("probe binding differs from retained " + key)
    if review.get("format") != "worker-red-x-independent-review-v1" or review.get("status") != "approved":
        raise ValueError("independent review approval required")
    for key, expected in (("source_draft_sha256", _sha(draft_path)),
                          ("native_probe_sha256", _sha(probe_path)),
                          ("probe_binding_sha256", _sha(binding_path))):
        if review.get(key) != expected:
            raise ValueError("independent review differs from retained " + key)
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("independent reviewer identity required")
    checks = review.get("checks")
    required = ("exact_public_highway_and_site", "official_device_original",
                "bus_facing_and_governed_lane_join", "official_design_matches_imported_asset")
    if not isinstance(checks, dict) or any(checks.get(key) is not True for key in required):
        raise ValueError("independent site, lane and design findings required")
    citations = review.get("citations")
    if not isinstance(citations, dict) or any(not isinstance(citations.get(key), str) or
            not citations[key].strip() for key in ("highway", "official_device", "native_display_state")):
        raise ValueError("independent original and Native design citations required")
    if probe.get("blueprint_readback") is not True or probe.get("rendered_pixels_reviewed") is not False:
        raise ValueError("unreviewed actual Native probe required")
    packet = {"review_status": "reviewed", "site": draft["site"]}
    for key in ("highway", "official_device"):
        item = draft[key]
        rel = item.get("source_path")
        if not isinstance(rel, str) or Path(rel).name != rel:
            raise ValueError(key + " retained source path invalid")
        source = draft_path.parent / rel
        if source.is_symlink() or not source.is_file() or _sha(source) != item.get("source_sha256"):
            raise ValueError(key + " original source missing or changed")
        if binding.get(key + "_source_sha256") != item["source_sha256"]:
            raise ValueError(key + " binding differs from original")
        packet[key] = {"source_path": rel, "source_sha256": item["source_sha256"],
                       "reviewer": reviewer, "source_citation": citations[key]}
    packet["highway"]["status"] = "public_highway_reviewed"
    packet["official_device"].update({
        "device_kind": "official_overhead_lane_signal", "symbol": "red_x",
        "faces_bus": True, "governed_lane_id": "red_lane",
        "native_asset_blueprint_id": probe["blueprint_id"],
        "native_display_state": {"attribute": probe["attribute"],
                                 "red_x_value": probe["red_x_value"],
                                 "source_citation": citations["native_display_state"]}})
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("draft", "probe", "binding", "review", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    packet = finalize(args.draft, args.probe, args.binding, args.review, args.output)
    print(json.dumps({"review_status": packet["review_status"],
                      "packet_sha256": _sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
