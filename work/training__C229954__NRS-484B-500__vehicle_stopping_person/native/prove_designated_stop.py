"""Synthetic CPU diagnostics for the source-bound designated-place meter."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from designated_stop import FRAMES, RATE_HZ, measure


def rectangle(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def packet(base, inside):
    base.mkdir(parents=True, exist_ok=True)
    stop_x = 10.0 if inside else 18.0
    rows = []
    for i in range(FRAMES):
        x = stop_x - max(0.0, 100 - i) * 0.05
        rows.append({"native_frame": i, "video_frame": i, "time_s": i / RATE_HZ,
                     "observed_speed_mps": 1.0 if i < 100 else 0.0,
                     "vehicle_footprint_map_m": rectangle(x - 1, -0.8, x + 1, 0.8)})
    result = {
        "format": "worker-designated-stop-native-packet",
        "sources": {},
        "device": {"device_id": "synthetic-device-1", "content": "synthetic no-stopping extent",
                   "authority_status": "source_reviewed_official", "erected": True,
                   "hazard_context_status": "physical_facts_retained_legal_unresolved",
                   "active_first_frame": 0, "active_last_frame": FRAMES - 1,
                   "designated_polygon_map_m": rectangle(8, -2, 12, 2)},
        "person_caused_stop_source": "synthetic driver controller timeline",
        "traffic_and_direction_source": "synthetic traffic and direction timeline",
        "rows": rows,
    }
    originals = {
        "designation": {"designated_polygon_map_m": result["device"]["designated_polygon_map_m"]},
        "device": {key: value for key, value in result["device"].items() if key != "designated_polygon_map_m"},
        "map": {"coordinate_system": "synthetic map metres", "fixture": "synthetic_native_sample"},
        "native_trace": rows,
        "video_frame_map": [{"video_frame": row["video_frame"], "time_s": row["time_s"]} for row in rows],
    }
    for name, data in originals.items():
        path = base / (name + ".json")
        path.write_text(json.dumps(data, separators=(",", ":")) + "\n")
        result["sources"][name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def rejected(original, mutation, message):
    test = copy.deepcopy(original)
    mutation(test)
    try:
        measure(test)
    except ValueError as error:
        if message not in str(error):
            raise AssertionError((message, str(error))) from error
        return str(error)
    raise AssertionError("Negative diagnostic was accepted: " + message)


def main():
    with tempfile.TemporaryDirectory(prefix="designated-stop-", dir=".runtime-work") as tmp:
        base = Path(tmp)
        inside = packet(base / "inside", True)
        outside = packet(base / "outside", False)
        # The two packets carry separate source identities and all 600 joins.
        a = measure(inside)
        b = measure(outside)
        assert a["rest_frames"] == b["rest_frames"] == 500
        assert a["rest_and_body_overlap_frames"] == 500
        assert b["rest_and_body_overlap_frames"] == 0
        assert a["body_overlap_at_any_rest_frame"] and not b["body_overlap_at_any_rest_frame"]
        negatives = {
            "missing_designation_source": rejected(inside, lambda p: p["sources"].pop("designation"), "original source reference"),
            "changed_designation_source": rejected(inside, lambda p: p["sources"]["designation"].__setitem__("sha256", "0" * 64), "original source"),
            "inactive_device": rejected(inside, lambda p: p["device"].__setitem__("active_last_frame", 200), "original device source"),
            "not_official": rejected(inside, lambda p: p["device"].__setitem__("authority_status", "unknown"), "original device source"),
            "missing_extent": rejected(inside, lambda p: p["device"].pop("designated_polygon_map_m"), "original extent source"),
            "missing_frame": rejected(inside, lambda p: p["rows"].pop(), "original trace source"),
            "bad_join": rejected(inside, lambda p: p["rows"][200].__setitem__("video_frame", 201), "original trace source"),
            "missing_person": rejected(inside, lambda p: p.__setitem__("person_caused_stop_source", ""), "Person-to-vehicle"),
            "missing_context": rejected(inside, lambda p: p.__setitem__("traffic_and_direction_source", ""), "direction context"),
        }
        print(json.dumps({"format": "worker-designated-stop-synthetic-proof", "inside": a,
                          "outside": b, "negative_rejections": negatives,
                          "source_type": "synthetic_native_sample", "legal_verdict": "none",
                          "physical_verdict": "none"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
