"""Original 20 Hz acquisition for the C135087 restricted-zone comparison.

An injected Native adapter owns actual simulator control and pixel acquisition.
The worker records its observations and refuses to seal partial source history.
"""

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from restricted_zone import construct
from reviewed_site import ROLES, validate


VIEWS = ("overview", "subject", "zone_access", "passenger_door")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def capture(adapter, plan, site_path, output, frame_count=900, allow_diagnostic=False):
    """Acquire original rows/pixels; physical and legal review remain separate."""
    if frame_count != 900:
        raise ValueError("exact capture requires 900 frames")
    provenance = adapter.provenance()
    if provenance != "original_native" and not (allow_diagnostic and provenance == "diagnostic_fixture"):
        raise ValueError("original Native provenance required")
    plan.validate()
    packet = validate(site_path, plan.case_id, plan)
    output = Path(output)
    if output.exists():
        if not (output / "construction.json").is_file() or (output / "original-attempt").exists():
            raise ValueError("refusing to overwrite an original attempt")
    else:
        output.mkdir(parents=True)
    original = output / "original-attempt"
    original.mkdir()
    source_dir = original / "source-review"
    source_dir.mkdir()
    copied = {}
    for role in ROLES:
        item = packet["sources"][role]
        source = Path(item["path"])
        if not source.is_absolute():
            source = Path(site_path).resolve().parent / source
        target = source_dir / (role + source.suffix)
        shutil.copy2(source, target)
        if _sha(target.read_bytes()) != item["sha256"]:
            raise ValueError("reviewed source changed during acquisition: " + role)
        copied[role] = {"path": "source-review/" + target.name, "sha256": item["sha256"]}
    sealed_packet = dict(packet, sources=copied)
    _json(original / "site-packet.json", sealed_packet)
    actors = None
    archives = {}
    rows = []
    traces = []
    video_frames = []
    first_frame = None
    first_time = None
    restored = False
    try:
        actors = construct(plan, adapter.world)
        cameras = adapter.attach_cameras(actors, VIEWS)
        if set(cameras) != set(VIEWS):
            raise ValueError("four original cameras missing")
        for view in VIEWS:
            archives[view] = zipfile.ZipFile(original / (view + ".zip"), "x",
                                             compression=zipfile.ZIP_STORED)
        for index in range(frame_count):
            adapter.request_control(actors, plan, index)
            sample = adapter.tick_and_read(actors, cameras)
            if not isinstance(sample, dict):
                raise ValueError("Native source sample missing")
            frame, time_s = sample.get("frame"), sample.get("time_s")
            if type(frame) is not int or type(time_s) not in (int, float):
                raise ValueError("original frame/time missing")
            if first_frame is None:
                first_frame, first_time = frame, time_s
            if frame != first_frame + index or abs(time_s - first_time - index / 20) > .005:
                raise ValueError("original Native frame/time gap")
            state = sample.get("state")
            required = ("subject_station_m", "subject_speed_mps", "entrant_station_m",
                        "entrant_speed_mps", "entrant_waiting", "passenger_exchange_active",
                        "passenger_station_m", "passenger_boarding_state",
                        "entrant_access_blocked", "entrant_parking_task_active")
            if not isinstance(state, dict) or any(key not in state for key in required):
                raise ValueError("original participant state/readback missing")
            if state.get("case_id") != plan.case_id or state.get("map_id") != plan.map_id:
                raise ValueError("original participant case/map readback mismatch")
            pixels = sample.get("camera_png")
            if not isinstance(pixels, dict) or set(pixels) != set(VIEWS):
                raise ValueError("four original pixel sources missing")
            pixel_sources = {}
            for view in VIEWS:
                data = pixels[view]
                if not isinstance(data, bytes) or not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("invalid original camera PNG")
                member = f"{index:04d}-{frame}.png"
                archives[view].writestr(member, data)
                pixel_sources[view] = {"member": member, "sha256": _sha(data)}
            trace, mapping = sample.get("trace"), sample.get("video_frame")
            if not isinstance(trace, dict) or trace.get("frame") != frame or \
                    trace.get("time_s") != time_s or not isinstance(mapping, dict) or \
                    mapping.get("video_frame") != index or mapping.get("carla_frame") != frame or \
                    mapping.get("time_s") != time_s:
                raise ValueError("original trace/video frame join missing")
            traces.append(trace)
            video_frames.append(mapping)
            rows.append(dict(frame=index, native_frame=frame, time_s=index / 20,
                             source_time_s=time_s, camera_sources=pixel_sources, **state))
        media = adapter.finalize_media(output, VIEWS, tuple(video_frames))
        if not isinstance(media, dict) or set(media) != set(VIEWS) | {"raw"} or \
                any(Path(media[name]).resolve() != (output / (name + ".mkv")).resolve() or
                    not Path(media[name]).is_file() or Path(media[name]).stat().st_size == 0
                    for name in media):
            raise ValueError("original encoded media incomplete")
    finally:
        for archive in archives.values():
            archive.close()
        if actors is not None and hasattr(actors, "close"):
            actors.close()
        restored = adapter.close() is True
    if len(rows) != frame_count or not restored:
        raise ValueError("original acquisition incomplete or world restoration unverified")
    history = original / "history.jsonl"
    history.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    (output / "trace.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                              for row in traces))
    (output / "video_frames.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                                     for row in video_frames))
    context = {"case_id": plan.case_id, "zone_start_m": plan.zone_start_m,
               "zone_end_m": plan.zone_end_m, "restricted_purpose": plan.restricted_purpose,
               "restricted_source": copied["zone_authority"],
               "effective_conditions": copied["effective_conditions"],
               "subject_vehicle_class_source": copied["subject_vehicle_class"],
               "driver_identity_source": copied["driver_identity"],
               "entrant_parking_purpose_source": copied["entrant_parking_task"],
               "prohibited_stopping_exclusions_review": copied["stopping_exclusions"]}
    _json(original / "context.json", context)
    _json(original / "seal.json", {"case_id": plan.case_id,
          "frames_sha256": _sha(history.read_bytes()),
          "context_sha256": _sha((original / "context.json").read_bytes()),
          "site_packet_sha256": _sha((original / "site-packet.json").read_bytes()),
          "camera_archives_sha256": {view: _sha((original / (view + ".zip")).read_bytes())
                                     for view in VIEWS},
          "trace_sha256": _sha((output / "trace.jsonl").read_bytes()),
          "video_frame_map_sha256": _sha((output / "video_frames.jsonl").read_bytes()),
          "encoded_media_sha256": {name: _sha((output / (name + ".mkv")).read_bytes())
                                   for name in (*VIEWS, "raw")},
          "diagnostic_fixture": provenance != "original_native",
          "physical_acceptance_claimed": False})
    return {"case_id": plan.case_id, "frame_count": frame_count,
            "physical_acceptance_claimed": False}
