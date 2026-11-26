"""Seal source-bound original ticks, four camera archives, and owner release."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from flagger_zone import CASES, SOURCES, number, point
from source_packet import ASSIGNMENT, sha, verify as verify_packet


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _adjacent(folder: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).name != name or name in (".", ".."):
        raise ValueError("capture source path must be adjacent")
    return folder / name


def seal(stage: Path, *, diagnostic_fixture: bool = False) -> dict:
    stage = Path(stage)
    packet_path = stage / "source-packet.json"
    verified = verify_packet(packet_path, diagnostic_fixture=diagnostic_fixture)
    packet = json.loads(packet_path.read_text())
    scene = packet["scene"]
    case_id = verified["case_id"]
    case = next(item for item in CASES if case_id == ASSIGNMENT + "__" + item.name)
    ticks_path = stage / "original-ticks.jsonl"
    ticks = [json.loads(line) for line in ticks_path.read_text().splitlines() if line.strip()]
    expected_frames = 3 if diagnostic_fixture else 900
    if len(ticks) != expected_frames:
        raise ValueError("source capture frame count differs")
    first_frame = ticks[0].get("original_frame")
    first_time = ticks[0].get("time_s")
    if type(first_frame) is not int or not number(first_time):
        raise ValueError("first original frame/time absent")
    for index, tick in enumerate(ticks):
        if (tick.get("original_frame") != first_frame + index or
                not number(tick.get("time_s")) or
                abs(tick["time_s"] - first_time - index / 20) > .005):
            raise ValueError("original 20 Hz frame/time join differs")
        for identity in ("driver_id", "vehicle_id", "flagger_id"):
            if tick.get(identity) != scene[identity]:
                raise ValueError("original participant identity differs: " + identity)
        for name in SOURCES:
            if tick.get(name + "_source_sha256") != verified["source_hashes"][name]:
                raise ValueError("original source context differs: " + name)
        if (tick.get("designated") is not case.designated or
                tick.get("authorized") is not case.authorized or
                not number(tick.get("vehicle_speed_mps")) or
                tick["vehicle_speed_mps"] < 0 or not point(tick.get("vehicle_xy"))):
            raise ValueError("original zone, authorization or vehicle motion differs")
        if scene["signal_frame"] <= index < scene["release_frame"]:
            if (tick.get("signal") != case.signal or
                    tick.get("signal_visible") is not True or
                    tick.get("intended_vehicle_id") != scene["vehicle_id"]):
                raise ValueError("active original flagger signal is not source-bound")
    camera_path = stage / "camera-source-manifest.json"
    cameras = json.loads(camera_path.read_text())
    if cameras.get("source_kind") != verified["source_kind"] or set(cameras.get("cameras", {})) != set(CAMERAS):
        raise ValueError("four original camera streams missing or provenance differs")
    checked = {}
    for name in CAMERAS:
        frames = cameras["cameras"][name]
        if not isinstance(frames, list) or len(frames) != expected_frames:
            raise ValueError("camera frame count differs: " + name)
        hashes = []
        dimensions = None
        for frame, tick in zip(frames, ticks):
            if (frame.get("original_frame") != tick["original_frame"] or
                    frame.get("time_s") != tick["time_s"]):
                raise ValueError("camera/tick timestamp differs: " + name)
            file = _adjacent(stage, frame.get("path"))
            if not file.is_file() or sha(file) != frame.get("sha256"):
                raise ValueError("original camera source bytes differ: " + name)
            with Image.open(BytesIO(file.read_bytes())) as image:
                image.verify()
            with Image.open(file) as image:
                if image.format != "PNG" or image.mode not in ("RGB", "RGBA"):
                    raise ValueError("original camera must be RGB/RGBA PNG: " + name)
                current = image.size
            if dimensions is None:
                dimensions = current
            elif dimensions != current:
                raise ValueError("camera dimensions changed within stream: " + name)
            hashes.append(frame["sha256"])
        checked[name] = {"frames": len(frames), "dimensions": list(dimensions),
                         "frame_sha256": hashes}
    release_path = stage / "native-owner-release.json"
    release = json.loads(release_path.read_text())
    if (release.get("case_id") != case_id or
            release.get("source_kind") != verified["source_kind"] or
            release.get("last_original_frame") != ticks[-1]["original_frame"] or
            release.get("world_restored") is not True or
            not isinstance(release.get("owned_actor_ids"), list) or
            not release["owned_actor_ids"] or
            release.get("destroyed_actor_ids") != list(reversed(release["owned_actor_ids"]))):
        raise ValueError("Native owner release or world restoration differs")
    return {"format": "c230235-capture-seal-v1", "case_id": case_id,
            "source_kind": verified["source_kind"],
            "packet_sha256": verified["packet_sha256"],
            "ticks_sha256": sha(ticks_path), "camera_manifest_sha256": sha(camera_path),
            "owner_release_sha256": sha(release_path),
            "first_original_frame": first_frame, "last_original_frame": ticks[-1]["original_frame"],
            "source_frame_count": len(ticks), "camera_sources": checked,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("capture seal output already exists")
    receipt = seal(args.stage, diagnostic_fixture=args.diagnostic_fixture)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(receipt["case_id"])
