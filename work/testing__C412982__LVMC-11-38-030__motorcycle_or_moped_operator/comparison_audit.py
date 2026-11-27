"""Independent original-only LVMC 11.38.030 controlled comparisons."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from sidewalk_030 import AID

GROUPS = {
    "sidewalk_sides": ("motorcycle_riding_sidewalk_north", "motorcycle_riding_sidewalk_south"),
    "device_classes": ("motorcycle_riding_sidewalk_north", "motor_scooter_riding_sidewalk"),
    "sidewalk_versus_road": ("motorcycle_riding_sidewalk_north", "motorcycle_riding_road"),
    "mounted_versus_walking": ("motorcycle_riding_sidewalk_north", "motorcycle_walking_sidewalk"),
    "city_boundary": ("motorcycle_riding_sidewalk_north", "motorcycle_riding_outside_city"),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_group(comparison_id, reports):
    suffixes = GROUPS.get(comparison_id)
    require(suffixes is not None, "unknown City sidewalk comparison")
    ids = [AID + "__" + suffix for suffix in suffixes]
    records = []
    for case_id in ids:
        report = reports.get(case_id)
        require(isinstance(report, dict) and report.get("format") == "worker-delivery-audit" and
                report.get("passed") is True and
                report.get("protocol_fixture_checked") is False and
                report.get("physical_acceptance_claimed") is True and
                report.get("case_id") == case_id and
                report.get("frame_count") == 900 and
                report.get("comparison_record", {}).get("source_kind") == "original_native_capture",
                "original accepted report required: " + case_id)
        records.append(report["comparison_record"])
    first, second = records
    for key in ("camera_plan", "duration_s"):
        require(first.get(key) and second.get(key) == first.get(key),
                "changed fixed original condition: " + key)
    if comparison_id != "city_boundary":
        require(first.get("fixed_source_sha256") and
                second.get("fixed_source_sha256") == first.get("fixed_source_sha256") and
                second.get("municipal_boundary_source_sha256") ==
                first.get("municipal_boundary_source_sha256"),
                "changed fixed original condition: site source")
    require(all(item.get("frame_count") == 900 and
                type(item.get("sidewalk_center_frames")) is int and
                type(item.get("road_center_frames")) is int and
                type(item.get("sidewalk_body_overlap_frames")) is int and
                type(item.get("road_body_overlap_frames")) is int for item in records),
            "original body surface measurements missing")
    for item in records:
        require(item.get("device_kind") in ("motorcycle", "motor_scooter") and
                item.get("operator_conduct") in ("riding", "walking") and
                item.get("surface") in ("sidewalk", "road") and
                item.get("side") in ("north", "south") and
                item.get("municipality"), "original comparison dimensions missing")
    if comparison_id == "sidewalk_sides":
        require([x["side"] for x in records] == ["north", "south"] and
                all(x["surface"] == "sidewalk" and x["sidewalk_body_overlap_frames"] > 0 and
                    x["device_kind"] == "motorcycle" and x["operator_conduct"] == "riding" and
                    x["municipality"] == "Las Vegas" for x in records),
                "two original City sidewalk sides not isolated")
    elif comparison_id == "device_classes":
        require([x["device_kind"] for x in records] == ["motorcycle", "motor_scooter"] and
                all(x["surface"] == "sidewalk" and x["side"] == "north" and
                    x["operator_conduct"] == "riding" and x["municipality"] == "Las Vegas" and
                    x["sidewalk_body_overlap_frames"] > 0 for x in records),
                "covered original device alternatives not isolated")
    elif comparison_id == "sidewalk_versus_road":
        require([x["surface"] for x in records] == ["sidewalk", "road"] and
                all(x["device_kind"] == "motorcycle" and x["operator_conduct"] == "riding" and
                    x["municipality"] == "Las Vegas" for x in records) and
                first["sidewalk_body_overlap_frames"] > 0 and
                second["sidewalk_body_overlap_frames"] == 0 and
                second["road_body_overlap_frames"] > 0,
                "original sidewalk versus road contrast absent")
    elif comparison_id == "mounted_versus_walking":
        require([x["operator_conduct"] for x in records] == ["riding", "walking"] and
                all(x["device_kind"] == "motorcycle" and x["surface"] == "sidewalk" and
                    x["municipality"] == "Las Vegas" and x["sidewalk_body_overlap_frames"] > 0
                    for x in records), "mounted riding versus walking contrast absent")
    else:
        require([x["municipality"] for x in records] == ["Las Vegas", "North Las Vegas"] and
                all(x["device_kind"] == "motorcycle" and x["operator_conduct"] == "riding" and
                    x["surface"] == "sidewalk" and x["sidewalk_body_overlap_frames"] > 0
                    for x in records), "original City boundary contrast absent")
    return {"format": "c412982-lvmc030-original-comparison-v1",
            "comparison_id": comparison_id, "case_ids": ids,
            "physical_comparison_passed": True, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-map", type=Path, required=True)
    parser.add_argument("--comparison", choices=tuple(GROUPS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = json.loads(args.report_map.read_text())
    reports = {cid: json.loads(Path(path).read_text()) for cid, path in paths.items()}
    answer = audit_group(args.comparison, reports)
    if args.output.exists():
        raise ValueError("refusing to overwrite prior comparison audit")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(answer, indent=2) + "\n")
    print(json.dumps(answer))


if __name__ == "__main__":
    main()
