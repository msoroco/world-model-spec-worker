"""Source-gated Native owner orchestration for flagger-zone capture.

The supplied adapter owns the concrete CARLA client and exposes original world
ticks and camera PNG bytes. This module never creates a diagnostic packet and
never substitutes configured values for observed signal or motion fields.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from capture_seal import CAMERAS, seal
from flagger_zone import CASES, construct
from source_packet import ASSIGNMENT, verify as verify_packet


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)


def acquire(adapter, packet_path: Path, output: Path, *, diagnostic_fixture: bool = False) -> dict:
    packet_path, output = Path(packet_path), Path(output)
    verified = verify_packet(packet_path, diagnostic_fixture=diagnostic_fixture)
    packet = json.loads(packet_path.read_text())
    scene = packet["scene"]
    case_id = verified["case_id"]
    case = next(item for item in CASES if case_id == ASSIGNMENT + "__" + item.name)
    if output.exists():
        raise ValueError("Native attempt output already exists")
    output.mkdir(parents=True)
    source_files = {packet_path.name} | {ref["path"] for ref in packet["source_refs"].values()}
    for name in source_files:
        shutil.copy2(packet_path.parent / name, output / name)
    if packet_path.name != "source-packet.json":
        (output / packet_path.name).rename(output / "source-packet.json")
    original_settings = adapter.snapshot_settings()
    owned = []
    restored = False
    rows = []
    cameras = {name: [] for name in CAMERAS}
    try:
        adapter.configure_sync(rate_hz=20)
        if adapter.readback_sync(rate_hz=20) is not True:
            raise ValueError("Native 20 Hz world settings readback failed")
        created = construct(adapter, scene, case)
        owned.extend(created["owned"])
        camera_actors = adapter.spawn_cameras(owned[-1], CAMERAS, scene)
        if (not isinstance(camera_actors, dict) or set(camera_actors) != set(CAMERAS) or
                any(actor is None for actor in camera_actors.values())):
            raise ValueError("four original camera actors required")
        owned.extend(camera_actors[name] for name in CAMERAS)
        frame_count = 3 if diagnostic_fixture else 900
        for index in range(frame_count):
            tick, images = adapter.tick_capture(index, scene, camera_actors)
            if not isinstance(tick, dict) or not isinstance(images, dict) or set(images) != set(CAMERAS):
                raise ValueError("original tick or camera observation missing")
            rows.append(tick)
            for name in CAMERAS:
                data = images[name]
                if not isinstance(data, bytes) or not data:
                    raise ValueError("original camera PNG bytes absent: " + name)
                file = output / f"{name}-{tick['original_frame']}.png"
                _write_exclusive(file, data)
                cameras[name].append({"original_frame": tick["original_frame"],
                                      "time_s": tick["time_s"],
                                      "path": file.name,
                                      "sha256": sha_bytes(data)})
        _write_exclusive(output / "original-ticks.jsonl",
                         "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode())
        _write_exclusive(output / "camera-source-manifest.json",
                         (json.dumps({"source_kind": verified["source_kind"],
                                      "cameras": cameras}, indent=2, sort_keys=True) + "\n").encode())
    finally:
        destroyed = []
        cleanup_errors = []
        for actor in reversed(owned):
            try:
                adapter.destroy(actor)
                destroyed.append(adapter.actor_id(actor))
            except Exception as error:
                cleanup_errors.append(str(error))
        try:
            adapter.restore_settings(original_settings)
            restored = adapter.readback_restored(original_settings) is True
        except Exception as error:
            cleanup_errors.append(str(error))
        if cleanup_errors:
            raise ValueError("Native owner cleanup failed: " + "; ".join(cleanup_errors))
    if not restored:
        raise ValueError("Native world settings were not restored")
    if not rows:
        raise ValueError("Native capture produced no original ticks")
    release = {"case_id": case_id, "source_kind": verified["source_kind"],
               "last_original_frame": rows[-1]["original_frame"],
               "world_restored": restored,
               "owned_actor_ids": [adapter.actor_id(actor) for actor in owned],
               "destroyed_actor_ids": destroyed}
    _write_exclusive(output / "native-owner-release.json",
                     (json.dumps(release, indent=2, sort_keys=True) + "\n").encode())
    return seal(output, diagnostic_fixture=diagnostic_fixture)
