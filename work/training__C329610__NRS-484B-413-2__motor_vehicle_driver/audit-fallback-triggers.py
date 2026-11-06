"""Independent raw-row audit of three synthetic fallback trigger crossings."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def audit(receipt):
    raw = (REPO / receipt["source_path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == receipt["source_sha256"]
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len(rows) == 800 and all(r["frame"] == i and r["time_s"] == i / 20 for i, r in enumerate(rows))
    assert [i for i, r in enumerate(rows) if r["course_change"]] == [420]
    onset = next(i for i, r in enumerate(rows) if r["signal"] == "left")
    assert all(r["signal"] == "left" for r in rows[onset:421])
    window = rows[onset:421]
    margin = rows[onset]["ego_xy_m"][0] - rows[0]["ego_xy_m"][0]
    error = max(r["route_error_m"] for r in window)
    fraction = sum(r["signal_visible"] for r in window) / len(window)
    assert abs(margin - receipt["runway_to_signal_onset_m"]) < 1e-8
    assert error == receipt["max_signal_window_route_error_m"]
    assert fraction == receipt["signal_visibility_fraction"]
    assert receipt["fallback1"] == (margin < 12)
    assert receipt["fallback2"] == (error > .35)
    assert receipt["fallback3"] == (fraction < .95)
    assert receipt["source_kind"] == "synthetic_cpu_fixture" and not receipt["dispatchable_observation"]
    return receipt


def main():
    summary = json.loads((HERE / "fallback-trigger-summary.json").read_text())
    base = audit(summary["base"])
    assert not any(base[f"fallback{i}"] for i in (1, 2, 3))
    assert set(summary["synthetic_positives"]) == {"fallback1", "fallback2", "fallback3"}
    for name, receipt in summary["synthetic_positives"].items():
        assert audit(receipt)[name]
    assert summary["changed_hash_rejected"] and summary["authored_request_rejected"]
    assert not summary["original_native_observed"]
    print(json.dumps({"base_negative":True,"positive_triggers":3,"source_hashes_checked":4,
                      "original_native_observed":False}))


if __name__ == "__main__":
    main()
