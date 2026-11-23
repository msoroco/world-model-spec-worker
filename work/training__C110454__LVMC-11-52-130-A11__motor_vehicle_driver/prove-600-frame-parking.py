"""Exercise the 30-second saved parking measurement with diagnostic Native-shaped rows."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / ".runtime-work" / "c110454-lvmc-600-frame"
spec = importlib.util.spec_from_file_location("measure_park", HERE / "native/measure_park.py")
measurement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurement)


def write(name, packet):
    path = OUT / (name + ".json")
    path.write_text(json.dumps(packet, allow_nan=False))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    rejected = {}
    for case, stop_x, relation in (("witness_1", 25.0, "outside_15_ft"),
                                    ("witness_2", 13.5, "within_15_ft")):
        frames = []
        for index in range(600):
            center_x = -70.0 + (stop_x + 70.0) * min(index, 499) / 499
            frames.append({"video_frame": index, "native_frame": 12000 + index,
                           "time_s": round(14.0 + index / 20, 5),
                           "body_xy_m": [[center_x - 2.6, -6.35], [center_x - 2.6, -4.15],
                                         [center_x + 2.6, -4.15], [center_x + 2.6, -6.35]],
                           "speed_m_s": 4.0 if index < 500 else 0.0})
        packet = {"source_kind": "native_frame_schema",
                  "intersection_boundary_source": "native_map_readback",
                  "intersection_entry_boundary_x_m": 7.0,
                  "synthetic_fixture": True, "frames": frames}
        source, digest = write(case, packet)
        value = measurement.measure(source, digest, 600)
        if value["sampled_relation"] != relation or value["source_frames"] != 600 or value["rest_frames"] != 100:
            raise AssertionError("30-second parking relation differs")
        results[case] = {"relation": relation,
                         "distance_m": value["nearest_parked_body_distance_m"],
                         "source_sha256": digest}
        variants = {
            "missing_frame": (250, "native_frame", -1, "join"),
            "wrong_time": (250, "time_s", 0.0, "join"),
            "bad_speed": (550, "speed_m_s", -1, "speed"),
            "no_rest": (550, "speed_m_s", 4.0, "parked interval"),
        }
        for label, (index, key, replacement, message) in variants.items():
            bad = json.loads(json.dumps(packet))
            bad["frames"][index][key] = replacement
            bad_source, bad_digest = write(case + "-" + label, bad)
            try:
                measurement.measure(bad_source, bad_digest, 600)
            except ValueError as error:
                if message not in str(error):
                    raise
            else:
                raise AssertionError(label + " negative passed")
            rejected[case + ":" + label] = message
        try:
            measurement.measure(source, "0" * 64, 600)
        except ValueError as error:
            if "hash" not in str(error):
                raise
        else:
            raise AssertionError("source hash negative passed")
        rejected[case + ":source_hash"] = "hash"
        try:
            measurement.measure(source, digest, 601)
        except ValueError as error:
            if "complete 601-frame" not in str(error):
                raise
        else:
            raise AssertionError("frame count negative passed")
        rejected[case + ":frame_count"] = "complete 601-frame"
    return {"passed": True, "diagnostic_only": True, "duration_s": 30,
            "rate_hz": 20, "frame_count": 600, "results": results,
            "negative_rejections": rejected, "physical_observation_claimed": False}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
