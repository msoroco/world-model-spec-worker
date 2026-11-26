"""Original 900-frame parked assembly acquisition through a reviewed adapter.

No fixture can enter this function. The local adapter owns CARLA actor, camera
and map calls; the worker CPU tests exercise the protocol only.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from projection_construction import build_and_readback
from projection_sources import CAMERAS, load_reviewed, sha, validate_native_adapter

HZ = 20
FRAMES = 900


def capture_original(adapter, packet_path, case_id, output_dir, *, candidate="primary",
                     pipeline_factory=None, seal_factory=None, adapter_module_path=None):
    packet_path = Path(packet_path).resolve()
    packet, site = load_reviewed(packet_path, case_id)
    out = Path(output_dir)
    if out.exists() and any((out / name).exists() for name in
                            ("capture-seal.json", "original-projection-history.jsonl",
                             "reviewed-packet")):
        raise ValueError("retain original attempt; choose fresh output")
    if pipeline_factory is None:
        from pipeline_capture import PipelineCapture
        pipeline_factory = PipelineCapture
    if seal_factory is None:
        from worker_exchange.native_output import seal_capture
        seal_factory = seal_capture
    out.mkdir(parents=True, exist_ok=True)
    reviewed = out / "reviewed-packet"
    reviewed.mkdir()
    shutil.copy2(packet_path, reviewed / "reviewed-site.json")
    if adapter_module_path is not None:
        module_path = validate_native_adapter(packet, adapter_module_path)
        shutil.copy2(module_path, reviewed / "native-adapter.py")
    for entry in packet["sources"].values():
        relative = Path(entry["path"])
        target = reviewed / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(packet_path.parent / relative, target)
        if sha(target) != entry["sha256"]:
            raise ValueError("reviewed original source changed during retention")
    built = pipeline = None
    started = finished = False
    rows = []
    joins = []
    try:
        built = build_and_readback(adapter, site, case_id, candidate=candidate)
        pipeline = pipeline_factory(adapter.pipeline_client(), built["owned"][0],
                                    out, case_id, required_observations=())
        adapter.start_cameras(out, packet["camera_plan"])
        started = True
        first_frame = first_time = None
        for index in range(FRAMES):
            adapter.hold_parked_assembly(built, index)
            frame, elapsed = adapter.tick_world()
            if type(frame) is not int or type(elapsed) not in (float, int):
                raise ValueError("original Native frame/time missing")
            if first_frame is None:
                first_frame, first_time = frame, elapsed
            if frame != first_frame + index or abs(elapsed - first_time - index / HZ) > .002:
                raise ValueError("original Native cadence or frame gap")
            camera_frames = adapter.camera_frame_ids(frame)
            if camera_frames != {name: frame for name in CAMERAS}:
                raise ValueError("four original cameras not frame-joined")
            captured = pipeline.capture(frame, elapsed)
            if captured.get("frame") != frame or captured.get("time_s") != elapsed:
                raise ValueError("PipelineCapture original frame join differs")
            sample = adapter.sample_parked_assembly(built, frame)
            if not isinstance(sample, dict):
                raise ValueError("original complete assembly sample missing")
            if (sample.get("physical_parts") is None or
                    sample.get("curb_segment_start_m") != site["curb_segment_start_m"] or
                    sample.get("curb_segment_end_m") != site["curb_segment_end_m"] or
                    sample.get("street_side_reference_m") != site["street_side_reference_m"]):
                raise ValueError("original complete part or curb readback missing")
            row = dict(sample, assignment_id=packet["assignment_id"],
                       case_id=case_id, frame=frame, time_s=index / HZ,
                       original_trace_id=adapter.trace_identity(),
                       reviewed_packet_sha256=sha(packet_path),
                       loaded_opendrive_sha256=site["opendrive_sha256"])
            if not row["original_trace_id"]:
                raise ValueError("original trace identity missing")
            rows.append(row)
            joins.append({"frame_index": index, "native_frame": frame,
                          "time_s": index / HZ, "camera_frames": camera_frames})
        videos = adapter.finish_cameras()
        finished = True
        if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
            raise ValueError("four original camera videos required")
        for name in CAMERAS:
            target = out / (name + ".mkv")
            if Path(videos[name]).resolve() != target.resolve() or not target.is_file() or target.stat().st_size == 0:
                raise ValueError("original camera video missing: " + name)
        pipeline.close(confirmed=True)
        (out / "original-projection-history.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        (out / "camera-frame-map.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in joins), encoding="utf-8")
        from worker_exchange.native_output import FrameMap
        with FrameMap(out / "video_frames.jsonl") as frame_map:
            for row in joins:
                frame_map.append(row["native_frame"], row["time_s"])
        (out / "reviewed-site.json").write_text(json.dumps(site, sort_keys=True) + "\n", encoding="utf-8")
    finally:
        try:
            if pipeline is not None and not pipeline.closed:
                pipeline.close(confirmed=False)
        finally:
            try:
                if started and not finished:
                    adapter.abort_cameras()
            finally:
                try:
                    if built is not None:
                        for actor in reversed(built["owned"]):
                            adapter.destroy(actor)
                finally:
                    if adapter.restore_world() is not True:
                        raise ValueError("original Native world restoration readback failed")
    (out / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "source_kind": "original_native", "physical_acceptance_claimed": False}) + "\n",
        encoding="utf-8")
    seal_factory(out, frames=FRAMES, restoration={
        "restored": True,
        "method": "owned actors and cameras destroyed; Native world settings readback"},
        errors=[], encoder_exit_codes={name: 0 for name in CAMERAS}, context={
            "case_id": case_id, "reviewed_packet_sha256": sha(packet_path),
            "candidate": candidate, "legal_boundary_m": 4.572,
            "physical_acceptance_claimed": False})
    return {"case_id": case_id, "frames": FRAMES,
            "original_history_sha256": sha(out / "original-projection-history.jsonl"),
            "capture_seal_sha256": sha(out / "capture-seal.json"),
            "physical_visibility_verified": False, "legal_verdict_claimed": False}
