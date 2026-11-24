"""Lazy Native encounter capture with original frame and camera joins.

The adapter owns CARLA and supplies tick(), observe(), camera_png(),
apply_control(), emergency_stop() and close(). This module never asserts that a
synthetic prop proves blindness or that an encounter satisfied the statute.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("blind_encounter", HERE / "blind_encounter.py")
encounter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = encounter
spec.loader.exec_module(encounter)
review_spec = importlib.util.spec_from_file_location("blind_reviewed_capture", HERE / "reviewed_sources.py")
reviewed = importlib.util.module_from_spec(review_spec)
sys.modules[review_spec.name] = reviewed
review_spec.loader.exec_module(reviewed)

CAMERAS = ("front", "left", "right", "rear")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_copy(source: Path, dest: Path, label: str) -> dict:
    source = source.resolve(strict=True)
    if source == dest.resolve():
        raise ValueError(f"{label} must be independent of capture destination")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not payload.get("source_sha256"):
        raise ValueError(f"{label} has no source provenance")
    shutil.copyfile(source, dest)
    return {"path": dest.name, "sha256": _sha(dest)}


def _control(case, row: dict, approach_speed_cap_mps: float = 2.0) -> dict:
    """Bounded engineering policy; contact is never a commanded action."""
    if not 0 < approach_speed_cap_mps <= 2.0:
        raise ValueError("Bounded approach speed cap required")
    if row["person_in_path"] and not row["person_clear"]:
        if case.response == "rolling" and row["body_gap_m"] > 8:
            target = min(0.5, approach_speed_cap_mps)
            speed = row["driver_speed_mps"]
            return {"throttle": 0.18 if speed < target - 0.08 else 0.0,
                    "brake": 0.15 if speed > target + 0.08 else 0.0,
                    "target_speed_mps": target}
        return {"throttle": 0.0, "brake": 1.0, "target_speed_mps": 0.0}
    if case.precaution == "wait_until_clear" and not row["person_clear"]:
        return {"throttle": 0.0, "brake": 1.0, "target_speed_mps": 0.0}
    speed = row["driver_speed_mps"]
    return {"throttle": 0.25 if speed < approach_speed_cap_mps - 0.1 else 0.0,
            "brake": 0.15 if speed > approach_speed_cap_mps + 0.1 else 0.0,
            "target_speed_mps": approach_speed_cap_mps}


def capture(adapter, case_id: str, output: Path, *, attestation: Path,
            carried_cue: Path, frame_count: int = 900,
            approach_speed_cap_mps: float = 2.0) -> dict:
    """Collect closed original sources for saved_encounter.process.

    Adapter tick returns the actual simulator frame identity and time. observe
    supplies body geometry and actor identities from that frame. camera_png
    supplies synchronized original bytes for each named camera. Every row and
    camera source is written before any saved-only measurement is attempted.
    """
    case = encounter.CASE_BY_ID[case_id]
    if frame_count != 900:
        raise ValueError("45 seconds at 20 Hz requires 900 original frames")
    if type(approach_speed_cap_mps) not in (int, float) or not 0 < approach_speed_cap_mps <= 2.0:
        raise ValueError("Bounded approach speed cap required")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("capture output must be empty")
    att = _source_copy(attestation, output / "blindness-attestation.json", "blindness attestation")
    cue = _source_copy(carried_cue, output / "carried-cue.json", "carried cue")
    att_data = json.loads((output / att["path"]).read_text(encoding="utf-8"))
    cue_data = json.loads((output / cue["path"]).read_text(encoding="utf-8"))
    if att_data.get("basis") not in ("wholly_blind", "partially_blind") or not att_data.get("issuer"):
        raise ValueError("independent blindness basis and issuer required")
    if cue_data.get("cue") != case.cue or cue_data.get("observation") != "actually_carried" or not cue_data.get("observer_source"):
        raise ValueError("actually carried cue source required")
    if att_data.get("person_actor_id") != cue_data.get("person_actor_id"):
        raise ValueError("protected person identity mismatch")
    for camera in CAMERAS:
        (output / camera).mkdir()
    rows = []
    media = []
    try:
        for index in range(frame_count):
            frame, time_s = adapter.tick()
            if not isinstance(frame, int) or isinstance(frame, bool):
                raise ValueError("Native frame identity missing")
            if rows and (frame != rows[-1]["frame"] + 1 or abs(time_s - rows[-1]["time_s"] - 0.05) > 0.002):
                raise ValueError("Native 20 Hz frame or time discontinuity")
            observed = adapter.observe(frame)
            if observed.get("person_actor_id") != att_data["person_actor_id"]:
                raise ValueError("observed protected person identity changed")
            if observed.get("frame") != frame:
                raise ValueError("Native observation frame mismatch")
            row = {"frame": frame, "time_s": time_s, **observed}
            for field in ("driver_speed_mps", "body_gap_m", "person_in_path", "person_clear", "contact", "precaution"):
                if field not in row:
                    raise ValueError(f"missing Native observation {field}")
            for camera in CAMERAS:
                source = adapter.camera_png(camera, frame)
                if not isinstance(source, bytes) or not source.startswith(PNG_SIGNATURE):
                    raise ValueError(f"missing original {camera} PNG at frame {frame}")
                path = output / camera / f"{frame:08d}.png"
                path.write_bytes(source)
                media.append({"frame": frame, "camera": camera, "path": str(path.relative_to(output)), "sha256": _sha(path)})
            rows.append(row)
            adapter.apply_control(_control(case, row, approach_speed_cap_mps))
        encounter.measure_saved(case_id, rows, attestation=att_data, cue_source=cue_data)
        history = output / "original-history.jsonl"
        history.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        # Preserve the same original samples under the canonical trace name.
        (output / "trace.jsonl").write_bytes(history.read_bytes())
        (output / "video_frames.jsonl").write_text(
            "".join(json.dumps({"video_frame": index, "carla_frame": row["frame"],
                                "native_frame": row["frame"], "time_s": row["time_s"]}) + "\n"
                    for index, row in enumerate(rows)), encoding="utf-8")
        media_map = output / "original-media-map.json"
        media_map.write_text(json.dumps(media, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest = {
            "assignment_id": HERE.name, "case_id": case_id,
            "original_frame_count": frame_count,
            "original_history": {"path": history.name, "sha256": _sha(history)},
            "blindness_attestation": att, "carried_cue": cue,
            "original_media_map": {"path": media_map.name, "sha256": _sha(media_map)},
            "capture_profile": {"hz": 20, "duration_s": 45, "cameras": list(CAMERAS)},
            "physical_acceptance_claimed": False,
        }
        (output / "saved-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest
    finally:
        adapter.emergency_stop()
        adapter.close()


def capture_reviewed(adapter, case_id: str, output: Path, *, source_packet: Path,
                     approach_speed_cap_mps: float = 2.0) -> dict:
    """Require a reviewed, hash-bound source packet before Native capture.

    Actor creation and CARLA world restoration remain the caller's responsibility.
    The adapter's live person identity is checked by capture against the packet.
    """
    source_packet = source_packet.resolve(strict=True)
    plan = reviewed.prepare(source_packet)
    if plan["case_id"] != case_id:
        raise ValueError("reviewed packet exact case mismatch")
    packet = json.loads(source_packet.read_text(encoding="utf-8"))
    root = source_packet.parent
    att = root / packet["blindness_attestation"]["path"]
    cue = root / packet["carried_cue"]["path"]
    output = Path(output)
    manifest = capture(adapter, case_id, output, attestation=att, carried_cue=cue,
                       approach_speed_cap_mps=approach_speed_cap_mps)
    if reviewed.prepare(source_packet)["reviewed_source_bindings"] != plan["reviewed_source_bindings"]:
        raise ValueError("reviewed original sources changed during Native capture")
    source_dir = output / "reviewed-source"
    if source_dir.exists():
        raise ValueError("reviewed source custody directory already exists")
    source_dir.mkdir()
    paths = [source_packet]
    for name in ("reviewed_map_route", "blindness_attestation", "carried_cue"):
        source = root / packet[name]["path"]
        paths.append(source)
        record = json.loads(source.read_text(encoding="utf-8"))
        if name != "reviewed_map_route":
            paths.append(root / record["original_source"]["path"])
    for source in paths:
        relative = source.relative_to(root)
        destination = source_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    map_source = root / packet["reviewed_map_route"]["path"]
    shutil.copyfile(map_source, output / "reviewed-map-route.json")
    retained = source_dir / source_packet.name
    copied = reviewed.prepare(retained)
    if copied["reviewed_source_bindings"] != plan["reviewed_source_bindings"]:
        raise ValueError("reviewed source custody copy differs")
    manifest["reviewed_source_packet"] = {
        "path": str(retained.relative_to(output)), "sha256": _sha(retained)}
    manifest["reviewed_source_bindings"] = plan["reviewed_source_bindings"]
    manifest["reviewed_map_id"] = plan["map_id"]
    (output / "saved-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
