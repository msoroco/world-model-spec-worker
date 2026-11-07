"""Independent raw-source audit of the six synthetic distance probes."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def rows_and_hash(relative, digest):
    raw = (REPO / relative).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    return [json.loads(line) for line in raw.splitlines()]


def main():
    summary = json.loads((HERE / "signal-fixture-summary.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = {c["case_id"]: c for c in plan["cases"]}
    assert len(summary["receipts"]) == len(cases) == 6
    assert not summary["selected"] and not summary["original_native_observed"]
    by_area = {}
    for item in summary["receipts"]:
        case = cases[item["case_id"]]
        receipt = item["measurement"]
        contract = case["synthetic_measurement_contract"]
        assert contract["source_sha256"] == receipt["source_sha256"]
        assert contract["measured_distance_ft"] == receipt["continuous_signal_distance_ft"]
        assert contract["expected_onset_frame"] == receipt["onset_frame"]
        rows = rows_and_hash(item["source_path"], receipt["source_sha256"])
        assert len(rows) == 800 and receipt["sample_count"] == 800
        assert all(r["frame"] == i and r["time_s"] == i / 20 for i, r in enumerate(rows))
        assert all(r["area"] == case["area_classification"] and r["weather"] == "clear" for r in rows)
        turns = [i for i, r in enumerate(rows) if r["course_change"]]
        assert turns == [420]
        onset = next(i for i, r in enumerate(rows) if r["signal"] == "left")
        assert all(r["signal"] == "left" for r in rows[onset:421])
        assert rows[419]["heading_deg"] == 0 and rows[445]["heading_deg"] < -30
        length = sum(math.dist(rows[i-1]["ego_xy_m"], rows[i]["ego_xy_m"])
                     for i in range(onset + 1, 421)) / .3048
        assert abs(length - case["requested_setting"]) < .5
        assert abs(length - receipt["continuous_signal_distance_ft"]) < 1e-8
        assert receipt["threshold_ft"] == (100 if case["area_classification"] == "business_or_residential" else 300)
        by_area.setdefault(case["area_classification"], []).append((case["requested_setting"], length, rows))
    assert sorted(x[0] for x in by_area["business_or_residential"]) == [90, 100, 110]
    assert sorted(x[0] for x in by_area["other"]) == [290, 300, 310]
    for group in by_area.values():
        base = group[0][2]
        for _, _, rows in group[1:]:
            assert [(r["ego_xy_m"], r["heading_deg"], r["course_change"], r["weather"]) for r in rows] == [
                (r["ego_xy_m"], r["heading_deg"], r["course_change"], r["weather"]) for r in base]
    controls = summary["weather_controls"]
    assert {item["requested_ft"] for item in controls} == {100, 300}
    assert summary["weather_control"] == {key: controls[0][key] for key in ("source_path", "measurement")}
    for wet in controls:
        wet_rows = rows_and_hash(wet["source_path"], wet["measurement"]["source_sha256"])
        dry_item = next(i for i in summary["receipts"] if i["requested_ft"] == wet["requested_ft"])
        dry_rows = rows_and_hash(dry_item["source_path"], dry_item["measurement"]["source_sha256"])
        assert len(wet_rows) == len(dry_rows) == 800
        assert all(a["weather"] == "rain" and {k:v for k,v in a.items() if k != "weather"} ==
                   {k:v for k,v in b.items() if k != "weather"} for a,b in zip(wet_rows,dry_rows))
        assert wet["measurement"]["continuous_signal_distance_ft"] == dry_item["measurement"]["continuous_signal_distance_ft"]
    print(json.dumps({"cases_audited":6,"weather_controls_audited":2,"comparison_groups":2,
                      "selected":False,"original_native_observed":False}))


if __name__ == "__main__":
    main()
