"""Independent measured C378809 goods and post-goods-idle comparisons."""
import argparse
import json
from pathlib import Path


PREFIX = "training__C378809__NRS-484B-477-1a__motor_vehicle_driver__probe_0"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(measured):
    require(set(measured) == {PREFIX + str(i) for i in (1, 2, 3)},
            "three exact alley measurement reports required")
    first, second, third = (measured[PREFIX + str(i)] for i in (1, 2, 3))
    for case_id, row in measured.items():
        require(row.get("case_id") == case_id and row.get("frame_count") == 600
                and row.get("source_kind") == "original_native_observation",
                "original case/frame measurement missing")
        require(row.get("legal_result") is None and row.get("expeditiousness") is None,
                "legal judgment substituted for measured result")
        require(row.get("stopped_in_alley_frames", 0) > 0 and
                row.get("sensor_rest_tolerance_mps") == .05,
                "observed alley stop missing")
    require(len({row["source_sha256"]["site-survey.json"] for row in measured.values()}) == 1
            and len({row["ordinance_status_source_id"] for row in measured.values()}) == 1,
            "fixed site or ordinance source changed")
    require(first["requested_goods_motion"] and not second["requested_goods_motion"]
            and third["requested_goods_motion"], "requested goods contrast changed")
    require(first["requested_idle_after_goods"] is False
            and third["requested_idle_after_goods"] is True,
            "requested post-goods idle contrast changed")
    require(first["observed_goods_event_ids"] and
            not second["observed_goods_event_ids"] and
            third["observed_goods_event_ids"],
            "independent original goods activity contrast missing")
    require(type(first.get("observed_stopped_after_goods_s")) in (int, float)
            and type(third.get("observed_stopped_after_goods_s")) in (int, float)
            and third["observed_stopped_after_goods_s"] >
                first["observed_stopped_after_goods_s"],
            "measured post-goods idle difference missing")
    return {"format": "c378809-independent-comparison-audit-v1",
            "case_ids": list(measured),
            "fixed_site_source_sha256": first["source_sha256"]["site-survey.json"],
            "fixed_ordinance_status_source_id": first["ordinance_status_source_id"],
            "goods_activity_contrast_observed": True,
            "post_goods_idle_difference_s":
                third["observed_stopped_after_goods_s"] -
                first["observed_stopped_after_goods_s"],
            "expeditiousness": None, "legal_result": None,
            "physical_acceptance": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurement", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    require(len(args.measurement) == 3, "three measurement files required")
    reports = [json.loads(Path(path).read_text()) for path in args.measurement]
    result = audit({report["case_id"]: report for report in reports})
    output = Path(args.output)
    require(not output.exists(), "retain previous comparison audit")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
