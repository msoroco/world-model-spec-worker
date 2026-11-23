"""Source-bound, saved-only C227824 entry measurement.

This processor reads an exited attempt. It cannot establish actual pixels or
physical completion; those require the separate delivery audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from entry_measurement import measure_entry


PACKETS = ("walker-body-history.jsonl", "signal-history.jsonl",
           "device-history.jsonl", "video_frames.jsonl",
           "camera-frame-joins.jsonl")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required(root, name):
    path = root / name
    if not path.is_file() or not path.stat().st_size:
        raise ValueError("missing saved source: " + name)
    return path


def _rows(path):
    try:
        rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid original packet: " + path.name) from exc
    if not rows:
        raise ValueError("empty original packet: " + path.name)
    return rows


def build_report(attempt):
    root = Path(attempt).resolve()
    scene_path = _required(root, "scene.json")
    scene = json.loads(scene_path.read_text())
    if scene.get("law_id") != "NRS-484B-307-8b" or scene.get("cell_id") != "C227824" or scene.get("actor") != "pedestrian":
        raise ValueError("wrong exact pedestrian scene")
    case_id = scene.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith("testing__C227824__NRS-484B-307-8b__pedestrian__"):
        raise ValueError("wrong exact case identity")
    provenance = json.loads(_required(root, "acquisition-provenance.json").read_text())
    kind = provenance.get("provenance_kind")
    fixture = provenance.get("diagnostic_fixture")
    if (kind, fixture) not in (("native", False), ("synthetic_fixture", True)):
        raise ValueError("contradictory acquisition provenance")
    if kind == "native":
        # Verify the immutable seal itself. A mutable provenance marker cannot
        # establish sealing and would invalidate its own sealed source hash.
        from delivery_audit import verify_seal
        verify_seal(root)
    source_hashes = {name: _sha(_required(root, name)) for name in ("scene.json", *PACKETS)}
    manifest = json.loads(_required(root, "acquisition.json").read_text())
    for name, digest in source_hashes.items():
        if manifest.get(name, {}).get("sha256") != digest:
            raise ValueError("saved source hash mismatch: " + name)
    for camera in CAMERAS:
        name = camera + ".mkv"
        digest = _sha(_required(root, name))
        source_hashes[name] = digest
        if manifest.get(name, {}).get("sha256") != digest:
            raise ValueError("saved source hash mismatch: " + name)
    packets = {name: _rows(root / name) for name in PACKETS}
    count = len(packets[PACKETS[0]])
    if count < 3 or any(len(rows) != count for rows in packets.values()):
        raise ValueError("incomplete synchronized original frame packets")
    samples = []
    for index in range(count):
        body, signal, device, frame_map, join = (packets[name][index] for name in PACKETS)
        frame, time_s = body.get("frame"), body.get("time_s")
        if frame_map.get("video_frame") != index or frame_map.get("carla_frame") != frame:
            raise ValueError("video and body frame join failed")
        if any(item.get("frame") != frame or item.get("time_s") != time_s
               for item in (signal, device, join)) or frame_map.get("time_s") != time_s:
            raise ValueError("signal, device, body and camera time join failed")
        if any(item.get("case_id") != case_id for item in (body, signal, device, join)):
            raise ValueError("original frame case identity differs")
        cameras = join.get("cameras")
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS) or any(
                cameras[name].get("frame") != frame for name in CAMERAS):
            raise ValueError("four original camera joins missing")
        samples.append({"frame": frame, "time_s": time_s,
                        "body_polygon_xy_m": body.get("body_polygon_xy_m"),
                        "facing_traffic_signal": signal.get("facing_traffic_signal"),
                        "other_devices": device.get("other_devices")})
    measured = measure_entry(samples, scene.get("highway_polygon_xy_m"))
    return {"format": "worker-saved-entry-measurement",
            "case_id": case_id, "provenance_kind": kind,
            "diagnostic_fixture": fixture, "sample_count": count,
            "measurement": measured, "source_sha256": source_hashes,
            "actual_pixels_verified": False,
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": report["case_id"],
                      "entry_observed": report["measurement"]["entry_observed"],
                      "diagnostic_fixture": report["diagnostic_fixture"]}))


if __name__ == "__main__":
    main()
