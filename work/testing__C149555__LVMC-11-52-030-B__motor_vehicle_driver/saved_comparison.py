"""Independent exact-pair freight comparison over sealed saved sources.

This checks observation and comparison isolation. It makes no legal finding and
does not turn a diagnostic fixture into an original recording.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from freight_contract import SourceError, audit_source_bundle, read_sealed, require_case_completion


ASSIGNMENT = "testing__C149555__LVMC-11-52-030-B__motor_vehicle_driver"
PAIRS = {
    "activity_direction": ("freight_loading", "freight_unloading", "observed_action"),
    "activity_presence": ("freight_loading", "no_freight_activity", "observed_action"),
    "commercial_status": ("freight_loading", "noncommercial_loading", "commercial_status_reviewed"),
    "posted_time": ("freight_loading", "outside_posted_time", "inside_posted_window"),
    "zone_footprint": ("freight_loading", "outside_yellow_zone", "stopped_inside_zone"),
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise SourceError(reason)


def audit_pair(left_manifest: dict, right_manifest: dict, comparison_id: str) -> dict:
    require(comparison_id in PAIRS, "unknown freight comparison")
    left_variant, right_variant, changed_measurement = PAIRS[comparison_id]
    packets = []
    measured = []
    for manifest, variant in ((left_manifest, left_variant), (right_manifest, right_variant)):
        case_id = f"{ASSIGNMENT}__{variant}"
        require(manifest.get("case_id") == case_id, "comparison exact case mismatch")
        require(manifest.get("kind") == "delivery", "comparison requires delivery source")
        require(manifest.get("acquisition_kind") == "original_native", "diagnostic source cannot satisfy delivery comparison")
        result = audit_source_bundle(manifest, case_id=case_id, variant=variant)
        require_case_completion(result)
        context_ref = manifest.get("sources", {}).get("comparison_context", {})
        require(context_ref.get("path") and context_ref.get("sha256"), "missing sealed comparison context")
        packet = read_sealed(context_ref["path"], context_ref["sha256"])
        native_ref = manifest["sources"]["native_result"]
        native = read_sealed(native_ref["path"], native_ref["sha256"])
        require(native.get("comparison_context_sha256") == context_ref["sha256"], "comparison context seal mismatch")
        require(packet.get("case_id") == case_id, "comparison context case mismatch")
        packets.append(packet)
        measured.append(result)

    left, right = packets
    fixed = (
        "native_map_sha256", "native_road_id", "native_lane_id", "curb_observation_sha256",
        "sign_observation_sha256", "zone", "posted_conditions", "camera_plan_sha256",
        "capture_rate_hz", "capture_frames", "ego_controller_sha256", "freight_prop_blueprint",
    )
    for key in fixed:
        require(left.get(key) is not None and left[key] == right.get(key), f"uncontrolled fixed condition: {key}")
    require(left["capture_rate_hz"] == 20 and left["capture_frames"] == 900, "comparison capture contract mismatch")

    # Cases may have different original recording files and actor IDs. Compare
    # source-bound observed dimensions, rather than identical trace bytes.
    dimensions = ("observed_action", "commercial_status_reviewed", "inside_posted_window", "stopped_inside_zone")
    for key in dimensions:
        equal = measured[0][key] == measured[1][key]
        require(not equal if key == changed_measurement else equal,
                f"comparison did not isolate {key}")
    require(measured[0]["stopped_outside_zone"] == (not measured[0]["stopped_inside_zone"]), "left zone classification incomplete")
    require(measured[1]["stopped_outside_zone"] == (not measured[1]["stopped_inside_zone"]), "right zone classification incomplete")

    # The commercial-status comparison necessarily changes the subject vehicle.
    # In other comparisons, a changed vehicle/dossier could confound the result.
    if comparison_id == "commercial_status":
        require(left.get("vehicle_id") != right.get("vehicle_id"), "commercial-status cases require distinct reviewed vehicles")
    else:
        require(left.get("vehicle_id") == right.get("vehicle_id"), "uncontrolled vehicle identity change")
        require(left.get("commercial_dossier_sha256") == right.get("commercial_dossier_sha256"), "uncontrolled commercial dossier change")
    if comparison_id != "posted_time":
        require(left.get("civil_time_source_sha256") == right.get("civil_time_source_sha256"), "uncontrolled civil-time source change")

    return {
        "format": "worker-freight-comparison-audit",
        "comparison_id": comparison_id,
        "case_ids": [left_manifest["case_id"], right_manifest["case_id"]],
        "source_integrity": True,
        "physical_case_completion": True,
        "fixed_conditions_checked": list(fixed),
        "deliberate_measurement": changed_measurement,
        "legal_conclusion": "unresolved",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True, choices=PAIRS)
    parser.add_argument("--left", required=True, type=Path)
    parser.add_argument("--right", required=True, type=Path)
    args = parser.parse_args()
    left = json.loads(args.left.read_text(encoding="utf-8"))
    right = json.loads(args.right.read_text(encoding="utf-8"))
    print(json.dumps(audit_pair(left, right, args.comparison), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
