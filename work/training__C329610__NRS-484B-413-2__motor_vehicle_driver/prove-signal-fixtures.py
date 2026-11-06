"""Generate six controlled synthetic signal captures and adversarial checks."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native.signal_measure import measure

HERE = Path(__file__).resolve().parent
OUT = HERE / "signal-fixtures"
TURN = 420
FRAMES = 800


def pose(i):
    if i <= TURN:
        return [-112 + .25 * i, 1.75], 0
    if i <= TURN + 55:
        progress = (i - TURN) / 55
        theta = math.pi / 2 * (1 - progress)
        return [-7 + 8.75 * math.cos(theta), -7 + 8.75 * math.sin(theta)], -90 * progress
    return [1.75, max(-48.25, -7 - .25 * (i - TURN - 55))], -90


def write_rows(path, rows):
    raw = b"".join((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode() for row in rows)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def reject(path, rows, area, onset):
    digest = write_rows(path, rows)
    try:
        measure(path, expected_sha256=digest, area=area,
                expected_onset_frame=onset, expected_course_change_frame=TURN)
    except ValueError:
        return
    raise AssertionError(f"negative passed: {path.name}")


def main():
    OUT.mkdir(exist_ok=True)
    plan = json.loads((HERE / "case-plan.json").read_text())
    assignment_hash = hashlib.sha256((HERE.parent.parent / "inputs" / plan["assignment_id"] / "assignment.json").read_bytes()).hexdigest()
    assert assignment_hash == plan["sources"][0]["sha256"]
    receipts = []
    for case in plan["cases"]:
        target = case["requested_setting"]
        area = "business_or_residential" if target < 200 else "other"
        onset = TURN - round(target * .3048 / .25)
        weather = "clear"
        rows = [{"frame": i, "time_s": i / 20, "ego_xy_m": pose(i)[0],
                 "signal": "left" if onset <= i <= 480 else "off", "course_change": i == TURN,
                 "area": area, "weather": weather, "heading_deg": pose(i)[1],
                 "route_error_m": .1, "signal_visible": True} for i in range(FRAMES)]
        path = OUT / (case["case_id"].split("__")[-1] + ".jsonl")
        digest = write_rows(path, rows)
        receipt = measure(path, expected_sha256=digest, area=area,
                          expected_onset_frame=onset, expected_course_change_frame=TURN)
        assert abs(receipt["continuous_signal_distance_ft"] - target) < .5
        assert receipt["sample_count"] == FRAMES
        receipts.append({"case_id": case["case_id"], "requested_ft": target, "measurement": receipt,
                         "source_path": str(path.relative_to(HERE.parent.parent)), "assignment_sha256": assignment_hash,
                         "provenance": "synthetic_cpu_fixture"})
        altered = [dict(r) for r in rows]
        altered[onset + 3]["signal"] = "off"
        reject(OUT / "negative-signal-gap.jsonl", altered, area, onset)
        altered = [dict(r) for r in rows]
        altered[17]["frame"] = 18
        reject(OUT / "negative-frame-gap.jsonl", altered, area, onset)
        altered = [dict(r) for r in rows]
        altered[TURN]["course_change"] = False
        reject(OUT / "negative-no-turn.jsonl", altered, area, onset)
        altered = [dict(r) for r in rows]
        altered[TURN]["area"] = "other" if area != "other" else "business_or_residential"
        reject(OUT / "negative-area.jsonl", altered, area, onset)
        path.write_bytes(path.read_bytes() + b" ")
        try:
            measure(path, expected_sha256=digest, area=area,
                    expected_onset_frame=onset, expected_course_change_frame=TURN)
        except ValueError:
            pass
        else:
            raise AssertionError("changed source hash accepted")
        write_rows(path, rows)
    for name in ("negative-signal-gap.jsonl", "negative-frame-gap.jsonl", "negative-no-turn.jsonl", "negative-area.jsonl"):
        (OUT / name).unlink()
    clear_path = OUT / "at_100_ft.jsonl"
    wet_rows = [json.loads(line) for line in clear_path.read_text().splitlines()]
    for row in wet_rows:
        row["weather"] = "rain"
    wet_path = OUT / "at_100_ft_rain.jsonl"
    wet_digest = write_rows(wet_path, wet_rows)
    wet = measure(wet_path, expected_sha256=wet_digest, area="business_or_residential",
                  expected_onset_frame=TURN - round(100 * .3048 / .25), expected_course_change_frame=TURN)
    assert wet["continuous_signal_distance_ft"] == next(r["measurement"]["continuous_signal_distance_ft"]
                                                    for r in receipts if r["requested_ft"] == 100)
    (HERE / "signal-fixture-summary.json").write_text(json.dumps({"format": "c329610-413-2-synthetic-proof-v1", "receipts": receipts,
          "weather_control": {"source_path": str(wet_path.relative_to(HERE.parent.parent)), "measurement": wet},
          "negative_checks_per_case": 5, "selected": False, "original_native_observed": False}, indent=2) + "\n")
    print(json.dumps({"cases": len(receipts), "weather_controls": 1, "negative_checks": 5 * len(receipts),
                      "distances_ft": [round(r["measurement"]["continuous_signal_distance_ft"], 3) for r in receipts]}))


if __name__ == "__main__":
    main()
