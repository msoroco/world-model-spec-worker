"""Source-bound physical completion check for entry and deliberate waiting.

This engineering check establishes the observed request pattern only. It does
not infer a legal permission or certify visibility in the recorded pixels.
"""
from __future__ import annotations

from entry_measurement import _polygon, polygons_overlap


def assess(report, scene, body_rows):
    if report.get("case_id") != scene.get("case_id"):
        raise ValueError("physical entry case identity differs")
    requested = scene.get("entry_request")
    if requested not in ("entry", "wait"):
        raise ValueError("physical entry request missing")
    polygon = _polygon(scene.get("highway_polygon_xy_m"))
    if not isinstance(body_rows, list) or len(body_rows) != report.get("sample_count") or len(body_rows) < 3:
        raise ValueError("physical entry body history incomplete")
    states = []
    previous = -1
    for row in body_rows:
        frame = row.get("frame")
        if type(frame) is not int or frame <= previous or row.get("case_id") != report["case_id"]:
            raise ValueError("physical entry original frame or case join failed")
        previous = frame
        states.append(polygons_overlap(row.get("body_polygon_xy_m"), polygon))
    if states[0]:
        raise ValueError("physical entry body begins inside highway")
    measured = report.get("measurement", {})
    event = measured.get("first_entry")
    if (event is None) != (not any(states)):
        raise ValueError("physical entry measurement disagrees with original bodies")
    if event is not None and event.get("frame") != body_rows[states.index(True)]["frame"]:
        raise ValueError("physical entry first-contact frame differs")
    met = (any(states) if requested == "entry" else not any(states))
    sources = report.get("source_sha256", {})
    names = ("scene.json", "walker-body-history.jsonl", "video_frames.jsonl")
    if any(not isinstance(sources.get(name), str) or len(sources[name]) != 64 for name in names):
        raise ValueError("physical entry source hashes missing")
    return {"status": "met" if met else "not_met",
            "method": "original full-body highway overlap across joined source frames",
            "intervals": [{"first_frame": body_rows[0]["frame"],
                           "last_frame": body_rows[-1]["frame"],
                           "first_time_s": body_rows[0]["time_s"],
                           "last_time_s": body_rows[-1]["time_s"]}],
            "sources": {name: sources[name] for name in names},
            "details": {"requested_entry": requested == "entry",
                        "entry_observed": any(states),
                        "sample_count": len(states)},
            "legal_verdict_claimed": False,
            "physical_causation_claimed": False}
