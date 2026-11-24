"""Positive and negative 30-second diagnostic CPU proof."""

from datetime import datetime, timedelta, timezone

from passenger_loading import FRAME_COUNT, FRAME_RATE, measure_loading, sign_effective


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


zone = {
    "kind": "passenger_curb_loading",
    "curb_source": "synthetic diagnostic curb geometry",
    "sign_source": "synthetic diagnostic sign text",
    "time_zone": "America/Los_Angeles",
    "hours_start": "08:00", "hours_end": "18:00",
}
base = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)
rows = []
for i in range(FRAME_COUNT):
    rows.append({
        "frame": i, "time_s": i / FRAME_RATE,
        "civil_timestamp": (base + timedelta(seconds=i / FRAME_RATE)).isoformat(),
        "vehicle_speed_mps": 0.0 if 80 <= i < 520 else 3.0,
        "vehicle_in_marked_zone": 80 <= i < 520,
        "door_open": 120 <= i < 350,
        "passenger_crossed_doorway": i == 240,
        "occupant_count": 1 if i < 240 else 2,
        "occupant_count_source": "synthetic_native_sample",
    })

assert sign_effective(base.isoformat(), zone)
measured = measure_loading(rows, zone)
assert measured["frames"] == 600 and measured["duration_s"] == 30.0
assert measured["transfer_during_halt_in_zone_frames"] == 1
assert measured["legal_expeditiousness_conclusion"] is None
assert measured["zone_validity_conclusion"] is None
reject(lambda: measure_loading(rows[:-1], zone), "600 frames")
bad = [dict(row) for row in rows]
bad[240]["time_s"] = 15.0
reject(lambda: measure_loading(bad, zone), "20 Hz join")
bad = [dict(row) for row in rows]
bad[240]["occupant_count_source"] = ""
reject(lambda: measure_loading(bad, zone), "occupant count source")
bad = [dict(row) for row in rows]
bad[240]["passenger_crossed_doorway"] = None
reject(lambda: measure_loading(bad, zone), "raw zone, door and passenger sources")
bad_zone = dict(zone)
bad_zone["sign_source"] = ""
reject(lambda: measure_loading(rows, bad_zone), "sign and time-zone provenance")
overnight = dict(zone, hours_start="20:00", hours_end="06:00")
assert sign_effective("2026-11-24T07:00:00+00:00", overnight)
assert not sign_effective("2026-11-23T18:00:00+00:00", overnight)
print("PASS: 600-frame passenger-loading timeline and sign-hours positive/negative CPU proof")
