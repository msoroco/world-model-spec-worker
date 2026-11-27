"""Independent original-only signed roadway comparison audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from signed_road import AID

GROUPS = {
    "sign_obedience": ("bicycle_disobey", "bicycle_obey"),
    "covered_device_alternatives": ("bicycle_disobey", "electric_bicycle_disobey",
                                    "electric_scooter_disobey"),
    "posting_observation": ("bicycle_disobey", "bicycle_sign_absent"),
    "signed_extent": ("bicycle_disobey", "bicycle_outside_extent"),
    "riding_versus_walking": ("bicycle_disobey", "bicycle_walking"),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_group(comparison_id, reports):
    suffixes = GROUPS.get(comparison_id)
    require(suffixes is not None, "unknown signed roadway comparison")
    ids = [AID + "__" + suffix for suffix in suffixes]
    records = []
    for case_id in ids:
        report = reports.get(case_id)
        require(isinstance(report, dict)
                and report.get("format") == "worker-delivery-audit"
                and report.get("passed") is True
                and report.get("protocol_fixture_checked") is False
                and report.get("physical_acceptance_claimed") is True
                and report.get("case_id") == case_id
                and report.get("frame_count") == 900
                and report.get("comparison_record", {}).get("source_kind") ==
                "original_native_capture", "original accepted report required: " + case_id)
        records.append(report["comparison_record"])
    first = records[0]
    for item in records[1:]:
        for key in ("fixed_source_sha256", "camera_plan", "duration_s"):
            require(first.get(key) and item.get(key) == first.get(key),
                    "changed fixed original condition: " + key)
    require(all(item.get("frame_count") == 900
                and type(item.get("roadway_center_frames")) is int
                and item["roadway_center_frames"] > 0
                and item.get("surface") == "roadway" for item in records),
            "original roadway motion measurements missing")
    if comparison_id == "sign_obedience":
        require([x["movement"] for x in records] == ["through", "turn_away"]
                and [x["extent"] for x in records] == ["within", "before"]
                and all(x["device_kind"] == "bicycle"
                        and x["operator_conduct"] == "riding"
                        and x["sign_state"] == "posted" for x in records),
                "signed movement contrast missing")
    elif comparison_id == "covered_device_alternatives":
        require([x["device_kind"] for x in records] ==
                ["bicycle", "electric_bicycle", "electric_scooter"]
                and all(x["operator_conduct"] == "riding"
                        and x["extent"] == "within"
                        and x["sign_state"] == "posted" for x in records),
                "three covered device alternatives missing")
    elif comparison_id == "posting_observation":
        require([x["sign_state"] for x in records] == ["posted", "absent"]
                and all(x["device_kind"] == "bicycle"
                        and x["extent"] == "within"
                        and x["operator_conduct"] == "riding" for x in records),
                "in-place sign contrast missing")
    elif comparison_id == "signed_extent":
        require([x["extent"] for x in records] == ["within", "outside"]
                and all(x["sign_state"] == "posted"
                        and x["device_kind"] == "bicycle" for x in records),
                "governed roadway extent contrast missing")
    elif comparison_id == "riding_versus_walking":
        require([x["operator_conduct"] for x in records] == ["riding", "walking"]
                and all(x["device_kind"] == "bicycle"
                        and x["extent"] == "within"
                        and x["sign_state"] == "posted" for x in records),
                "riding versus walking contrast missing")
    return {"format": "c412927-signed-road-original-comparison-v1",
            "comparison_id": comparison_id, "case_ids": ids,
            "fixed_source_sha256": first["fixed_source_sha256"],
            "physical_comparison_passed": True, "legal_verdict_claimed": False}


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
