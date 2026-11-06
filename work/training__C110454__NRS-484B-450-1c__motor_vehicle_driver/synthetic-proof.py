"""Adversarial 480-frame CPU fixture for the saved parking measurement path."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from engineering import evaluate_trigger
from geometry import STOP_X, body, check, overlap_area_xy
from measure import measure


def save(path: Path, rows: list[dict]) -> str:
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample(suffix: str, index: int) -> dict:
    stop = STOP_X[suffix]
    # First 240 frames are motion; the final 240 are a sustained deliberate stop.
    fraction = min(index / 239, 1.0)
    x = round(-50 + (stop + 50) * fraction, 5)
    return {"video_frame": index, "native_frame": 1000 + index,
            "time_s": index / 20, "body_xy_m": body(x),
            "speed_m_s": 4.0 if index < 240 else 0.0,
            "native_intersection_survey": True,
            "exception_source": {"other_traffic_actor_count": 0,
                                 "native_signal_count": 0,
                                 "authored_law_direction_count": 0},
            "exceptions": {"traffic_conflict": False, "lawful_direction": False,
                           "police_direction": False, "traffic_device": False}}


def expect_reject(path: Path, rows: list[dict], reason: str) -> None:
    digest = save(path, rows)
    try:
        measure(path, digest)
    except ValueError as exc:
        if reason not in str(exc):
            raise AssertionError(f"Expected {reason}, saw {exc}") from exc
    else:
        raise AssertionError("Corrupt source accepted")


def main() -> None:
    geometry = check()
    with tempfile.TemporaryDirectory(prefix="c110454-450-1c-") as temp:
        tmp = Path(temp)
        outcomes = {}
        for suffix, expected in (("probe_a", "outside_intersection"),
                                 ("probe_b", "within_intersection")):
            path = tmp / f"{suffix}.jsonl"
            rows = [sample(suffix, i) for i in range(480)]
            digest = save(path, rows)
            result = measure(path, digest)
            if result["parking_relation"] != expected or result["parked_frames"] != 240:
                raise AssertionError("Positive relation or duration differs")
            outcomes[suffix] = result
            corrupt = [r.copy() for r in rows]
            corrupt[200] = corrupt[200] | {"native_frame": 1300}
            expect_reject(tmp / "frame-gap.jsonl", corrupt, "Native frame gap")
            for exception in ("traffic_conflict", "lawful_direction",
                              "police_direction", "traffic_device"):
                corrupt = [r.copy() for r in rows]
                corrupt[300] = corrupt[300] | {"exceptions": rows[300]["exceptions"] | {exception: True}}
                expect_reject(tmp / (exception + ".jsonl"), corrupt, "Unexcluded exception")
            corrupt = [r.copy() for r in rows]
            corrupt[300] = corrupt[300] | {"exception_source": rows[300]["exception_source"] |
                            {"other_traffic_actor_count": 1}}
            expect_reject(tmp / "source-count.jsonl", corrupt, "Exception source counts")
            corrupt = [r.copy() for r in rows]
            corrupt[400] = corrupt[400] | {"native_intersection_survey": False}
            expect_reject(tmp / "survey.jsonl", corrupt, "Native intersection survey absent")
            path.write_bytes(path.read_bytes() + b" ")
            try: measure(path, digest)
            except ValueError as exc:
                if "hash differs" not in str(exc): raise
            else: raise AssertionError("Source mutation accepted")
        # Measurement-trigger logic is exercised on a hash-pinned synthetic record,
        # without representing it as an original observation.
        triggers = {}
        for candidate, key, positive, negative in (
            ("fallback1", "max_cross_track_error_m", .6, .2),
            ("fallback2", "mean_final_park_speed_m_s", .3, .1),
            ("fallback3", "min_vehicle_pixel_margin_px", 25, 80)):
            record = {"source_kind": "original_native_and_video", key: positive}
            source = tmp / "metrics.json"
            source.write_text(json.dumps(record))
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if not evaluate_trigger(candidate, source, digest): raise AssertionError(candidate)
            source.write_text(json.dumps(record | {key: negative}))
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if evaluate_trigger(candidate, source, digest): raise AssertionError(candidate)
            triggers[candidate] = "positive_and_negative_synthetic_pass"
    if geometry["probes"]["probe_a"]["authored_intersection_overlap_m2"] != 0 or \
       geometry["probes"]["probe_b"]["authored_intersection_overlap_m2"] < 10:
        raise AssertionError("Controlled authored geometry differs")
    print(json.dumps({"passed": True, "scope": "authored and synthetic CPU only",
                      "geometry": geometry, "saved_measurement": outcomes,
                      "fallback_triggers": triggers,
                      "negative_tests_per_case": 8}, indent=2))


if __name__ == "__main__": main()
