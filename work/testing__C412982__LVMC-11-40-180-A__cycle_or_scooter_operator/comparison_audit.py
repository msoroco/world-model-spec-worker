"""Independent original-only Fremont branch and held-condition comparisons."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fremont_180 import AID

GROUPS = {
    "sidewalk_side": ("bicycle_riding_north", "bicycle_riding_south"),
    "covered_device_alternatives": ("bicycle_riding_north",
                                    "electric_bicycle_riding_north",
                                    "electric_scooter_riding_north"),
    "riding_versus_walking": ("bicycle_riding_north", "bicycle_walking_north"),
    "sidewalk_versus_road": ("bicycle_riding_north", "bicycle_riding_road"),
    "municipal_extent": ("bicycle_riding_north", "bicycle_riding_before_main",
                         "bicycle_riding_after_seventh"),
    "posting_observation": ("bicycle_riding_north", "bicycle_riding_sign_absent"),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_group(comparison_id, reports):
    suffixes = GROUPS.get(comparison_id)
    require(suffixes is not None, "unknown Fremont comparison")
    ids = [AID + "__" + suffix for suffix in suffixes]
    records = []
    for case_id in ids:
        report = reports.get(case_id)
        require(isinstance(report, dict) and
                report.get("format") == "worker-delivery-audit" and
                report.get("passed") is True and
                report.get("protocol_fixture_checked") is False and
                report.get("physical_acceptance_claimed") is True and
                report.get("case_id") == case_id and
                report.get("frame_count") == 900 and
                report.get("comparison_record", {}).get("source_kind") ==
                "original_native_capture",
                "original accepted report required: " + case_id)
        records.append(report["comparison_record"])
    first = records[0]
    for item in records[1:]:
        for key in ("fixed_source_sha256", "camera_plan", "duration_s"):
            require(first.get(key) and item.get(key) == first.get(key),
                    "changed fixed original condition: " + key)
    require(all(item.get("frame_count") == 900 for item in records),
            "original frame count differs")
    require(all(type(item.get("sidewalk_center_frames")) is int and
                type(item.get("road_center_frames")) is int for item in records),
            "original body surface measurements missing")
    if comparison_id == "sidewalk_side":
        require([x["side"] for x in records] == ["north", "south"] and
                all(x["surface"] == "sidewalk" and x["sidewalk_center_frames"] > 0
                    for x in records) and
                len({x["device_kind"] for x in records}) == 1 and
                len({x["operator_conduct"] for x in records}) == 1,
                "two original sidewalk sides not isolated")
    elif comparison_id == "covered_device_alternatives":
        require([x["device_kind"] for x in records] ==
                ["bicycle", "electric_bicycle", "electric_scooter"] and
                all(x["operator_conduct"] == "riding" and x["side"] == "north" and
                    x["extent"] == "between" and x["sidewalk_center_frames"] > 0
                    for x in records),
                "three named original device alternatives not isolated")
    elif comparison_id == "riding_versus_walking":
        require([x["operator_conduct"] for x in records] == ["riding", "walking"] and
                all(x["device_kind"] == "bicycle" and x["sidewalk_center_frames"] > 0
                    for x in records),
                "original riding versus walking contrast absent")
    elif comparison_id == "sidewalk_versus_road":
        require([x["surface"] for x in records] == ["sidewalk", "road"] and
                records[0]["sidewalk_center_frames"] > 0 and
                records[1]["sidewalk_center_frames"] == 0 and
                records[1]["road_center_frames"] > 0,
                "original sidewalk versus road contrast absent")
    elif comparison_id == "municipal_extent":
        require([x["extent"] for x in records] ==
                ["between", "before_main", "after_seventh"] and
                all(x["surface"] == "sidewalk" and x["sidewalk_center_frames"] > 0
                    for x in records),
                "Main-to-Seventh original extent contrast absent")
    elif comparison_id == "posting_observation":
        require([x["sign_state"] for x in records] == ["posted", "absent"] and
                all(x["device_kind"] == "bicycle" and x["extent"] == "between" and
                    x["operator_conduct"] == "riding" for x in records),
                "original area posting contrast absent")
    return {"format": "c412982-fremont-original-comparison-v1",
            "comparison_id": comparison_id, "case_ids": ids,
            "fixed_source_sha256": first["fixed_source_sha256"],
            "physical_comparison_passed": True,
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-map", type=Path, required=True)
    parser.add_argument("--comparison", choices=tuple(GROUPS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = json.loads(args.report_map.read_text())
    reports = {case_id: json.loads(Path(path).read_text())
               for case_id, path in paths.items()}
    answer = audit_group(args.comparison, reports)
    if args.output.exists():
        raise ValueError("refusing to overwrite prior comparison audit")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(answer, indent=2) + "\n")
    print(json.dumps(answer))


if __name__ == "__main__":
    main()
