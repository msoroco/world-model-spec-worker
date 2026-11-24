"""Deterministic 30-second source-shaped timing proofs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("prior_signal_meter", HERE / "prior_signal_meter.py")
meter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meter)


def packet(signal_first=150, rear=True, stop=False):
    rows = []
    for frame in range(600):
        if stop:
            speed = max(0.0, 8.0 - max(0, frame - 200) * 0.2)
        else:
            speed = 12.0 if frame < 200 else max(6.0, 12.0 - (frame - 199) * 0.2)
        rows.append({"frame": frame, "sim_time_s": frame / 20, "ego_speed_mps": speed,
                     "rear_surface_gap_m": 8.0 if rear else 100.0, "rear_same_lane": rear,
                     "rear_behind": rear, "signal_request": "brake_lamp" if signal_first is not None and frame >= signal_first else "none",
                     "signal_observed": signal_first is not None and frame >= signal_first,
                     "ego_velocity_source_ref": "native/actor/ego/velocity",
                     "ego_pose_source_ref": "native/actor/ego/transform",
                     "ego_extent_source_ref": "native/actor/ego/bbox",
                     "rear_pose_source_ref": "native/actor/rear/transform",
                     "rear_extent_source_ref": "native/actor/rear/bbox",
                     "signal_source_ref": "native/actor/ego/control-and-lamp-observation"})
    return {"format": "prior-signal-native-source-v1", "rate_hz": 20,
            "deceleration_probe_mps2": -2.0, "frames": rows}


def reject(value, message):
    try:
        meter.measure(value)
    except ValueError as exc:
        assert message in str(exc), str(exc)
        return
    raise AssertionError("missing source was accepted")


def main():
    prior = meter.measure(packet(150))
    same = meter.measure(packet(200))
    omitted = meter.measure(packet(None))
    no_rear = meter.measure(packet(150, rear=False))
    stopped = meter.measure(packet(150, stop=True))
    assert prior["event_frame"] == 200 and prior["signal_first_frame"] == 150
    assert prior["signal_precedes_event"] and prior["signal_lead_frames"] == 50
    assert same["event_frame"] == 200 and not same["signal_precedes_event"]
    assert omitted["signal_first_frame"] is None and not omitted["signal_precedes_event"]
    assert no_rear["rear_at_event"]["same_lane"] is False
    assert stopped["event_kind"] in ("stop", "sudden_slow_probe")
    bad = packet(); bad["frames"][200].pop("rear_pose_source_ref")
    reject(bad, "rear_pose_source_ref")
    bad = packet(); bad["frames"][200].pop("signal_source_ref")
    reject(bad, "signal_source_ref")
    bad = packet(); bad["frames"][200]["sim_time_s"] += 0.1
    reject(bad, "frame map")
    digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = {"format": "prior-signal-cpu-proof-v1", "assignment_id": "training__C230259__NRS-484B-413-3__motor_vehicle_driver",
              "rate_hz": 20, "frames": 600, "positive_and_negative_tests": 8,
              "cases": {key: {"source_packet_sha256": item["source_packet_sha256"],
                               "measurement_sha256": digest(item), "event_frame": item["event_frame"],
                               "signal_first_frame": item["signal_first_frame"],
                               "signal_precedes_event": item["signal_precedes_event"],
                               "rear_at_event": item["rear_at_event"]}
                        for key, item in (("prior", prior), ("same_frame", same), ("omitted", omitted),
                                          ("no_rear", no_rear), ("stop", stopped))},
              "missing_source_rejections": ["rear_pose_source_ref", "signal_source_ref", "noncanonical frame map"],
              "simulation_started": False, "physical_status": "unverified", "legal_verdict": None}
    path = HERE / "prior-signal-proof.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "proof": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
