"""Synchronous original-source capture for C109035 emergency device comparisons.

The caller supplies a reviewed site, real device command/readback adapters and
independent dispatch/equipment documents. CARLA does not expose siren sound as a
standard vehicle-light state, so missing physical readback is a hard error.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from emergency_scene import control_plan
from native_scene import create

PREFIX = "testing__C109035__NRS-484D-400-5__emergency_vehicle_driver__"
FRAMES = 900
HZ = 20


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source(output: Path, name: str, value: bytes) -> dict:
    path = output / name
    if path.exists() or path.is_symlink():
        raise ValueError("Original source already exists: " + name)
    path.write_bytes(value)
    return {"path": name, "sha256": _sha(value)}


def _document(path: Path, *, kind: str, case_id: str) -> bytes:
    data = Path(path).read_bytes()
    obj = json.loads(data)
    if obj.get("case_id") != case_id or obj.get("source_kind") != kind:
        raise ValueError("Independent document identity mismatch: " + kind)
    if not obj.get("reviewer") or not obj.get("source_citation"):
        raise ValueError("Independent document review missing: " + kind)
    if kind == "dispatch_context" and (obj.get("source_status") != "documented" or not obj.get("event_interval_frames")):
        raise ValueError("Dispatch event source undocumented")
    if kind == "equipment_record" and (not obj.get("authorization_source") or not obj.get("device_installation_source")):
        raise ValueError("Equipment source undocumented")
    return data


def capture(world, carla_api, *, case_id: str, site_packet: Path,
            dispatch_document: Path, equipment_document: Path, output: Path,
            device_command, device_readback, drive_step, camera_capture) -> dict:
    """Drive 45 seconds at 20 Hz and seal original source files.

    device_command(ego, siren=bool, lamps=bool) requests hardware state.
    device_readback(ego) must return independently observed booleans, source
    citations and a source type; it cannot merely echo the command.
    drive_step(ego, pedestrian, tick) owns motion control; camera_capture
    retains the synchronized four original camera frames externally and returns
    their source references. All adapters are supplied at invocation.
    """
    if not case_id.startswith(PREFIX):
        raise ValueError("Exact assignment case ID required")
    suffix = case_id[len(PREFIX):]
    plan = control_plan(suffix)
    dispatch = _document(dispatch_document, kind="dispatch_context", case_id=case_id)
    equipment = _document(equipment_document, kind="equipment_record", case_id=case_id)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("Capture output must be empty")
    actors = create(world, carla_api, site_packet, case_id)
    ego, pedestrian = actors["ego"], actors["pedestrian"]
    rows = []
    cameras = []
    first_timestamp = None
    prior_frame = None
    try:
        for tick in range(FRAMES):
            elapsed = tick / HZ
            siren = bool(plan["siren_command_window_s"] and plan["siren_command_window_s"][0] <= elapsed <= plan["siren_command_window_s"][1])
            lamps = bool(plan["warning_lamp_command_window_s"] and plan["warning_lamp_command_window_s"][0] <= elapsed <= plan["warning_lamp_command_window_s"][1])
            drive_step(ego, pedestrian, tick)
            device_command(ego, siren=siren, lamps=lamps)
            native_frame = world.tick()
            snapshot = world.get_snapshot()
            if native_frame != snapshot.frame or (prior_frame is not None and native_frame != prior_frame + 1):
                raise ValueError("Native frame gap or snapshot mismatch")
            prior_frame = native_frame
            if first_timestamp is None:
                first_timestamp = snapshot.timestamp.elapsed_seconds
            actual_elapsed = snapshot.timestamp.elapsed_seconds - first_timestamp
            if not math.isfinite(actual_elapsed) or abs(actual_elapsed - elapsed) > 0.003:
                raise ValueError("Native frame timing not 20 Hz")
            observed = device_readback(ego)
            if not isinstance(observed, dict) or type(observed.get("siren_active")) is not bool or type(observed.get("warning_lamp_active")) is not bool:
                raise ValueError("Independent device readback missing")
            if observed.get("source_type") in (None, "", "command_echo") or not observed.get("source_citation"):
                raise ValueError("Independent device-state source missing")
            camera_ref = camera_capture(native_frame)
            if not isinstance(camera_ref, dict) or set(camera_ref) != {"front", "rear", "left", "right"} or not all(camera_ref.values()):
                raise ValueError("Four synchronized camera source references missing")
            cameras.append({"frame": tick, "native_frame": native_frame, "sources": camera_ref})
            rows.append({"frame": tick, "native_frame": native_frame, "elapsed_s": elapsed,
                         "siren_commanded": siren, "warning_lamp_commanded": lamps,
                         "siren_active": observed["siren_active"],
                         "warning_lamp_active": observed["warning_lamp_active"],
                         "device_source_type": observed["source_type"],
                         "device_source_citation": observed["source_citation"]})
        trace = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()
        camera_data = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in cameras).encode()
        sources = {
            "device_trace": _source(out, "device_trace.jsonl", trace),
            "camera_trace": _source(out, "camera_trace.jsonl", camera_data),
            "dispatch_context": _source(out, "dispatch_context.json", dispatch),
            "equipment_record": _source(out, "equipment_record.json", equipment),
        }
        receipt = {"case_id": case_id, "source_kind": "original_capture",
                   "site_packet_sha256": actors["site_packet_sha256"], "sources": sources,
                   "native_first_frame": rows[0]["native_frame"],
                   "native_last_frame": rows[-1]["native_frame"],
                   "physical_acceptance_claimed": False}
        _source(out, "capture_receipt.json", (json.dumps(receipt, indent=2, sort_keys=True) + '\n').encode())
        return receipt
    finally:
        try:
            device_command(ego, siren=False, lamps=False)
        finally:
            pedestrian.destroy()
            ego.destroy()
