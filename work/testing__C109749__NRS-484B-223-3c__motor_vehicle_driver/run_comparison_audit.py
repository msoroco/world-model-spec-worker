"""Audit four independently saved exact attempts for one declared comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from center_lane_site import validate_site
from comparison_audit import audit_merge_observation, audit_numeric_triple
from delivery_audit import audit_saved_delivery
from saved_finalizer import finalize_saved

SUFFIXES = ("below_50ft", "at_50ft", "above_50ft", "no_merge")
COMPARISONS = ("post_turn_center_lane_distance", "merge_observation")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def read_attempt(root, case_id, diagnostic, production_shape=False):
    root = Path(root).resolve()
    if not root.is_dir() or root.name != "original-attempt":
        raise ValueError("Independent original-attempt directory required")
    receipt = json.loads((root / "native/capture-receipt.json").read_text())
    if receipt.get("case_id") != case_id:
        raise ValueError("Comparison original attempt selects another exact case")
    if diagnostic or production_shape:
        marker = json.loads((root.parent / "fixture-provenance.json").read_text())
        if marker.get("diagnostic_fixture") is not True:
            raise ValueError("Diagnostic comparison requires explicit synthetic provenance")
        if not production_shape:
            checked = audit_saved_delivery(root, receipt)
            if checked["verified_frame_count"] != 900:
                raise ValueError("Diagnostic comparison needs 900 original source frames")
            measured = checked["measured"]
        else:
            checked = finalize_saved(root, case_id, 900)
            measured = checked
    else:
        # Full production path decodes and hashes all 3,600 original PNGs.
        checked = finalize_saved(root, case_id, 900)
        measured = checked
    site = json.loads((root / "native/site-packet.json").read_text())
    verified_site = validate_site(site)
    trace = json.loads((root / "native/trace.json").read_text())
    actor_ids = {row.get("receiving_vehicle_actor_id") for row in trace["samples"]}
    if len(actor_ids) != 1 or None in actor_ids:
        raise ValueError("Original receiving traffic actor identity incomplete")
    receiving = next(row for row in site["lanes"] if row["id"] == verified_site["receiving_lane_id"])
    return {
        "original_trace_source": str((root / "native/trace.json").resolve()),
        "original_trace_sha256": receipt["original_trace"]["sha256"],
        "native_map_sha256": site["native_map_source"]["sha256"],
        "highway_review_sha256": site["highway_review_source"]["sha256"],
        "lane_design_sha256": receipt["site_source"]["sha256"],
        "entry_route_sha256": digest({"entry_maneuver": site["entry_maneuver"],
                                      "target": site["entry_target_lane_id"]}),
        "receiving_vehicle_route_sha256": digest({"lane": receiving["centreline_xy_m"],
                                                   "actor_id": next(iter(actor_ids))}),
        "camera_plan_sha256": digest({"views": ["overview", "approach", "reference_corner",
                                                "driver_reference"], "fps": 20}),
        "distance_ft": measured["distance_ft"], "boundary_ft": 50.0,
        "merge_observed": measured["merge_observed"], "merge_frame": measured["merge_frame"],
        "censored": measured["censored"],
    }


def audit(attempts, comparison_id, diagnostic=False, production_shape=False):
    base = Path(__file__).resolve().parent
    if set(attempts) != set(SUFFIXES):
        raise ValueError("Comparison needs four distinct exact attempt paths")
    rows = {suffix: read_attempt(attempts[suffix], base.name + "__" + suffix,
                                 diagnostic, production_shape)
            for suffix in SUFFIXES}
    if comparison_id == COMPARISONS[0]:
        result = audit_numeric_triple({name: rows[name] for name in SUFFIXES[:3]})
    elif comparison_id == COMPARISONS[1]:
        result = audit_merge_observation(rows["below_50ft"], rows["no_merge"])
    else:
        raise ValueError("Unknown declared comparison ID")
    return {"format": "worker-comparison-source-audit", "comparison_id": comparison_id,
            "result": result, "source_trace_sha256": {key: row["original_trace_sha256"]
                                                     for key, row in rows.items()},
            "diagnostic_fixture": bool(diagnostic or production_shape),
            "full_original_png_shape_checked": bool(production_shape or not diagnostic),
            "physical_acceptance_claimed": False,
            "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True, choices=COMPARISONS)
    parser.add_argument("--attempt", action="append", required=True,
                        help="One suffix=original-attempt path; supply all four")
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--production-shape", action="store_true",
                        help="Decode all original pixels of an explicit synthetic CPU fixture")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    attempts = {}
    for item in args.attempt:
        suffix, separator, source = item.partition("=")
        if not separator or suffix in attempts:
            raise ValueError("Duplicate or malformed exact attempt argument")
        attempts[suffix] = source
    if args.diagnostic and args.production_shape:
        raise ValueError("Select one diagnostic audit path")
    result = audit(attempts, args.comparison, args.diagnostic, args.production_shape)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"comparison_id": args.comparison,
                      "diagnostic_fixture": args.diagnostic or args.production_shape,
                      "full_original_png_shape_checked": args.production_shape,
                      "passed": True}))


if __name__ == "__main__":
    main()
