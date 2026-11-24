"""CPU-only source and boundary tests; generated rows are diagnostic fixtures."""

import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from night_parking import measure


ROOT = Path(".runtime-work/C229398-night-parking")
OUT = Path("work/training__C229398__LVMC-11-52-300__nonmotor_vehicle_operator/native/night-parking-proof.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(folder, seconds, *, local_start="2026-11-23T01:10:00", device_class="qualifying_nonmotor_vehicle", bad_frame=None):
    folder.mkdir()
    observations = folder / "raw-frame-observations.jsonl"
    start = datetime.fromisoformat(local_start).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    first = round(start.timestamp() * 1000)
    count = seconds * 20 + 1
    with observations.open("w") as stream:
        for frame in range(count):
            stream.write(json.dumps({
                "frame": frame + (1 if frame == bad_frame else 0),
                "utc_epoch_ms": first + frame * 50,
                "actor_velocity_mps": 0.0,
                "actor_center_xy_m": [40.0, -7.0],
            }, separators=(",", ":")) + "\n")
    sources = {}
    packets = {
        "classification": {"device_class": device_class, "classification_status": "diagnostic_invented"},
        "street": {"street_bounds_xy_m": [0.0, 100.0, -10.0, 10.0], "geometry_status": "diagnostic_invented"},
        "parking": {"activity_annotation": "parked", "annotation_status": "diagnostic_invented"},
        "civil_clock": {"timezone": "America/Los_Angeles", "clock_status": "diagnostic_invented"},
    }
    for name in packets:
        path = folder / (name + ".txt")
        path.write_text(json.dumps(packets[name]) + "\n")
        sources[name] = {"path": str(path), "sha256": digest(path)}
    sources["frame_map"] = {"path": str(observations), "sha256": digest(observations)}
    provenance = folder / "provenance.json"
    provenance.write_text(json.dumps({
        "format": "worker-night-parking-provenance",
        "mode": "diagnostic",
        "timezone": "America/Los_Angeles",
        "expected_frame_count": count,
        "sources": sources,
    }, indent=2) + "\n")
    return observations, provenance


def rejected(obs, prov, expected):
    try:
        measure(obs, prov)
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError("Expected diagnostic rejection: " + expected)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        base = Path(temporary)
        below = measure(*fixture(base / "below", 1799))
        exact = measure(*fixture(base / "exact", 1800))
        above = measure(*fixture(base / "above", 1801))
        motor = measure(*fixture(base / "motor", 1801, device_class="motor_vehicle"))
        outside = measure(*fixture(base / "outside", 1801, local_start="2026-11-23T06:01:00"))
        assert below["longest_continuous_qualifying_ms"] == 1799000 and below["observed_duration_over_thirty_minutes"] is False
        assert exact["longest_continuous_qualifying_ms"] == 1800000 and exact["observed_duration_over_thirty_minutes"] is False
        assert above["longest_continuous_qualifying_ms"] == 1801000 and above["observed_duration_over_thirty_minutes"] is True
        assert motor["observed_duration_over_thirty_minutes"] is None
        assert outside["longest_continuous_qualifying_ms"] == 0 and outside["observed_duration_over_thirty_minutes"] is False
        gap_obs, gap_prov = fixture(base / "gap", 12, bad_frame=25)
        gap_rejection = rejected(gap_obs, gap_prov, "Incomplete or nonmonotonic frame map")
        stale_obs, stale_prov = fixture(base / "stale", 12)
        stale_obs.write_text(stale_obs.read_text() + "\n")
        hash_rejection = rejected(stale_obs, stale_prov, "Source hash mismatch: frame_map")
        clock_obs, clock_prov = fixture(base / "clock", 12)
        clock_path = base / "clock" / "civil_clock.txt"
        clock_path.write_text(json.dumps({"timezone": "UTC"}) + "\n")
        clock_data = json.loads(clock_prov.read_text())
        clock_data["sources"]["civil_clock"]["sha256"] = digest(clock_path)
        clock_prov.write_text(json.dumps(clock_data) + "\n")
        clock_rejection = rejected(clock_obs, clock_prov, "Civil clock source differs")
        proof = {
            "format": "worker-night-parking-cpu-proof",
            "passed": True,
            "fixture_kind": "synthetic diagnostic, no CARLA or real recording",
            "checks": {
                "below_30_min_ms": below["longest_continuous_qualifying_ms"],
                "exact_30_min_ms": exact["longest_continuous_qualifying_ms"],
                "above_30_min_ms": above["longest_continuous_qualifying_ms"],
                "motor_vehicle_result": motor["observed_duration_over_thirty_minutes"],
                "outside_window_ms": outside["longest_continuous_qualifying_ms"],
                "gap_rejection": gap_rejection,
                "stale_source_rejection": hash_rejection,
                "clock_source_rejection": clock_rejection,
            },
            "measurer_sha256": digest(Path(__file__).with_name("night_parking.py")),
            "physical_or_legal_acceptance": False,
        }
        OUT.write_text(json.dumps(proof, indent=2) + "\n")
        print(json.dumps(proof))


if __name__ == "__main__":
    main()
