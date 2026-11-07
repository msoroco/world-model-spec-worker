"""Recompute six signaling baselines and isolated fallback crossings from raw rows."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def inspect(receipt):
    path = REPO / receipt["source_path"]
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == receipt["source_sha256"]
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len(rows) == 800
    assert [row["frame"] for row in rows] == list(range(800))
    assert all(row["time_s"] == index / 20 for index, row in enumerate(rows))
    assert [i for i, row in enumerate(rows) if row["course_change"]] == [420]
    onset = next(i for i, row in enumerate(rows) if row["signal"] == "left")
    assert all(row["signal"] == "left" for row in rows[onset:421])
    window = rows[onset:421]
    margin = rows[onset]["ego_xy_m"][0] - rows[0]["ego_xy_m"][0]
    maximum = max(row["route_error_m"] for row in window)
    fraction = sum(row["signal_visible"] for row in window) / len(window)
    assert abs(margin - receipt["runway_to_signal_onset_m"]) < 1e-9
    assert maximum == receipt["max_signal_window_route_error_m"]
    assert fraction == receipt["signal_visibility_fraction"]
    assert [receipt[f"fallback{i}"] for i in (1, 2, 3)] == [margin < 12, maximum > .35, fraction < .95]
    assert receipt["source_kind"] == "synthetic_cpu_fixture"
    assert receipt["dispatchable_observation"] is False
    return rows, onset, (margin, maximum, fraction)


def main():
    proof = json.loads((HERE / "case-trigger-coverage.json").read_text())
    assert proof["format"] == "c329610-413-2-case-trigger-coverage-v1"
    assert len(proof["cases"]) == 6 and proof["selected"] is False
    assert proof["original_native_or_pixels_observed"] is False
    assert proof["fallback1_requested_start_extension_m"] == 4
    assert proof["fallback1_requested_runway_m_above_300_ft"] == 14.512
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    case = next(row for row in manifest["cases"] if row["case_id"].endswith("__above_300_ft"))
    alternate = next(row for row in case["candidates"] if row["id"] == "fallback1")
    def request(reference):
        path = HERE / reference["construction"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == reference["construction_sha256"]
        files = json.loads(path.read_text())["files"]
        config = next(row["content"] for row in files if row["path"] == "config.json")
        return json.loads(config)["native_request"]
    primary, fallback = request(case), request(alternate)
    assert primary["start_x_m"] == -112 and fallback["start_x_m"] == -116
    assert primary["signal_onset_x_m"] == fallback["signal_onset_x_m"]
    assert fallback["signal_onset_x_m"] - fallback["start_x_m"] == proof["fallback1_requested_runway_m_above_300_ft"]
    assert len({item["case"] for item in proof["cases"]}) == 6
    triggered = []
    for item in proof["cases"]:
        baseline, onset, metrics = inspect(item["baseline"])
        tracking, tracking_onset, tmetrics = inspect(item["tracking_crossing"])
        visibility, visibility_onset, vmetrics = inspect(item["visibility_crossing"])
        assert tracking_onset == visibility_onset == onset
        assert len(baseline) == len(tracking) == len(visibility)
        assert [r for i, r in enumerate(tracking) if r != baseline[i]] == [tracking[onset + 10]]
        assert tracking[onset + 10]["route_error_m"] == .5
        assert tmetrics[0] == metrics[0] and tmetrics[2] == metrics[2] and tmetrics[1] == .5
        changed = [i for i, (a, b) in enumerate(zip(baseline, visibility)) if a != b]
        assert changed == list(range(onset, onset + 20))
        assert all(visibility[i]["signal_visible"] is False for i in changed)
        assert vmetrics[0] == metrics[0] and vmetrics[1] == metrics[1] and vmetrics[2] < .95
        assert item["baseline"]["fallback2"] is False and item["baseline"]["fallback3"] is False
        assert item["tracking_crossing"]["fallback2"] is True
        assert item["visibility_crossing"]["fallback3"] is True
        if item["baseline"]["fallback1"]:
            triggered.append(item["case"])
    assert triggered == ["above_300_ft"]
    print(json.dumps({"passed": True, "cases": 6, "baseline_fallback1_triggered": triggered,
                      "isolated_tracking_crossings": 6, "isolated_visibility_crossings": 6,
                      "original_native_or_pixels_observed": False}))


if __name__ == "__main__":
    main()
