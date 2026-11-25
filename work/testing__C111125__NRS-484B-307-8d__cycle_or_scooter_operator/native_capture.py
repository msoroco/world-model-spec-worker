"""CARLA-lazy writer for synchronized original bicycle and four-camera readbacks.

The caller owns the world and samples it after each tick. This writer records
what the adapters observed; it does not claim that requested signal or detector
policies physically occurred.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image


BASE = Path(__file__).resolve().parent
ASSIGNMENT_ID = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
PROFILE_SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
                 "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _signal_trial():
    spec = importlib.util.spec_from_file_location("c111125_signal_trial_capture", BASE / "signal_trial.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path, value: dict | list) -> dict:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_saved(*, attempt_root: Path, authority_root: Path, site: dict,
                  case_suffix: str, actor_id: int, observed_blueprint_id: str,
                  policy_receipt: dict, sample_tick, native_exit_code: int,
                  frame_count: int = 900,
                  diagnostic_fixture: bool = False) -> dict:
    """Seal a completed sequence of original 20 Hz samples.

    ``sample_tick(index)`` must return ``(readback, camera_png_bytes)`` after a
    Native tick. A failure leaves no completed receipt and never fabricates a
    missing frame. The owner must release its CARLA resources separately.
    """
    trial = _signal_trial()
    plan = trial.construct_plan(site, Path(authority_root), case_suffix)
    if not isinstance(actor_id, int) or observed_blueprint_id != site.get("ego_blueprint_id"):
        raise ValueError("Native bicycle actor readback missing")
    if not isinstance(policy_receipt, dict) or policy_receipt.get("device_sha256") != plan["device_sha256"] or policy_receipt.get("detector_sha256") != plan["detector_sha256"]:
        raise ValueError("source-bound detector/device policy receipt missing")
    if native_exit_code != 0:
        raise ValueError("Native completion failed; attempt cannot be sealed")
    if frame_count < 2:
        raise ValueError("capture needs at least two observed frames")
    if not diagnostic_fixture and frame_count != 900:
        raise ValueError("original delivery requires exactly 900 observed frames")
    root = Path(attempt_root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    archives = {name: ZipFile(root / f"camera-{name}.zip", "w", compression=ZIP_STORED) for name in CAMERAS}
    rows = []
    try:
        first_frame = None
        first_time = None
        for index in range(frame_count):
            row, images = sample_tick(index)
            if not isinstance(row, dict) or not isinstance(images, dict) or set(images) != set(CAMERAS):
                raise ValueError("synchronized four-camera readback missing")
            frame = row.get("frame")
            stamp = row.get("timestamp_s")
            if not isinstance(frame, int) or not isinstance(stamp, (int, float)):
                raise ValueError("original frame identity or timestamp missing")
            if first_frame is None:
                first_frame, first_time = frame, stamp
            if frame != first_frame + index or abs(stamp - first_time - index / 20) > 0.001:
                raise ValueError("original 20 Hz frame/time sequence broken")
            image_refs = {}
            for name in CAMERAS:
                payload = images[name]
                if not isinstance(payload, bytes):
                    raise ValueError("original camera PNG bytes missing")
                with Image.open(BytesIO(payload)) as image:
                    image.verify()
                with Image.open(BytesIO(payload)) as image:
                    if image.format != "PNG":
                        raise ValueError("original camera image is not PNG")
                    image.load()
                    if not diagnostic_fixture and image.size != PROFILE_SIZES[name]:
                        raise ValueError("original camera does not match capture profile: " + name)
                member = f"{frame:08d}.png"
                archives[name].writestr(member, payload)
                image_refs[name] = {"member": member, "sha256": hashlib.sha256(payload).hexdigest()}
            rows.append({**row, "camera_frames": image_refs})
    finally:
        for archive in archives.values():
            archive.close()
    native = _json(root / "native.json", {"frames": rows, "blueprint_class": "bicycle"})
    device = _json(root / "device.json", {"frames": [
        {"frame": row["frame"], "subject_signal": row.get("subject_signal"), "cross_signal": row.get("cross_signal")} for row in rows]})
    detector = _json(root / "detector.json", {"frames": [
        {"frame": row["frame"], "occupied": row.get("detector_occupied"), "output": row.get("detector_output")} for row in rows]})
    geometry = _json(root / "geometry.json", {"stop_boundary_station_m": plan["stop_boundary_station_m"],
                                           "entry_station_m": plan["entry_station_m"]})
    packet = {"case_suffix": case_suffix, "blueprint_class": "bicycle", "actor_id": actor_id,
              "observed_blueprint_id": observed_blueprint_id, "policy_receipt": policy_receipt,
              "device_sha256": plan["device_sha256"], "map_sha256": plan["map_sha256"],
              "frames": rows, "native_trace_ref": native, "device_trace_ref": device,
              "detector_trace_ref": detector, "geometry_ref": geometry}
    packet_ref = _json(root / "packet.json", packet)
    camera_sources = {name: {"path": f"camera-{name}.zip",
                             "sha256": _hash_file(root / f"camera-{name}.zip"),
                             "frame_count": frame_count} for name in CAMERAS}
    receipt = {"format": "c111125-native-attempt-v1", "case_id": ASSIGNMENT_ID + "__" + case_suffix,
               "diagnostic_fixture": diagnostic_fixture, "native_exit_code": native_exit_code,
               "actor_id": actor_id, "observed_blueprint_id": observed_blueprint_id,
               "policy_receipt": policy_receipt, "packet_ref": packet_ref,
               "frame_count": frame_count, "camera_sources": camera_sources,
               "camera_capture_complete": True}
    _json(root / "attempt.json", receipt)
    return receipt
