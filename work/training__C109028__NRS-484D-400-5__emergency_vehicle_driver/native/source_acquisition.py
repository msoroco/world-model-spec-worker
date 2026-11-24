"""Validate independently acquired siren and dispatch evidence for C109028.

The actuator request is never an observation. This module joins a microphone
recording, reviewed per-frame audio observations, and original dispatch records.
An audio observation is a documented human/source review, not a CARLA flag or
an automatic legal conclusion. The 500-foot equipment-capability question stays
unknown until a qualified normal-condition acoustic test is supplied.
"""
from __future__ import annotations

import hashlib
import json
import math
import wave
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
WINDOW_S = FRAMES / RATE_HZ


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError("Expected 600 source rows: " + path.name)
    return rows


def validate_audio(wav_path, observations_path, frame_map_path):
    """Check original microphone bytes and reviewed observations against Native time."""
    wav_path, observations_path = Path(wav_path), Path(observations_path)
    if not wav_path.is_file():
        raise ValueError("Missing original microphone recording")
    with wave.open(str(wav_path), "rb") as stream:
        channels, width, rate, samples = (stream.getnchannels(),
                                           stream.getsampwidth(),
                                           stream.getframerate(),
                                           stream.getnframes())
    if channels != 1 or width != 2 or rate != 48000 or samples != 48000 * WINDOW_S:
        raise ValueError("Microphone WAV must be 30 s mono PCM16 at 48 kHz")
    audio_hash = sha(wav_path)
    rows, mapping = read_rows(observations_path), read_rows(frame_map_path)
    observed = []
    for index, (row, frame) in enumerate(zip(rows, mapping)):
        t = (index + 1) / RATE_HZ
        if (row.get("source_kind") != "independent_microphone_review" or
                row.get("audio_sha256") != audio_hash or
                row.get("native_frame") != frame.get("native_frame") or
                frame.get("video_frame") != index or
                type(row.get("siren_audible")) is not bool or
                not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip() or
                any(type(value) not in (int, float) or not math.isfinite(value) or
                    abs(value - t) > 1e-4 for value in
                    (row.get("time_s"), frame.get("time_s")))):
            raise ValueError("Independent audio observation/frame join differs")
        observed.append(row["siren_audible"])
    return {"source_kind": "independent_microphone_review",
            "audio_sha256": audio_hash, "observations_sha256": sha(observations_path),
            "frame_map_sha256": sha(frame_map_path),
            "reviewed_siren_audible_frames": sum(observed),
            "siren_audible_by_frame": observed,
            "audible_at_500_ft_verified": False,
            "physical_legal_verdict": None}


def validate_dispatch(record_path, frame_map_path, document_path):
    """Require an original response/pursuit document; requested flags never count."""
    record_path, document_path = Path(record_path), Path(document_path)
    if not document_path.is_file():
        raise ValueError("Missing original dispatch/authorization document")
    document_hash = sha(document_path)
    rows, mapping = read_rows(record_path), read_rows(frame_map_path)
    for index, (row, frame) in enumerate(zip(rows, mapping)):
        t = (index + 1) / RATE_HZ
        if (row.get("source_kind") != "original_dispatch_record" or
                row.get("document_sha256") != document_hash or
                row.get("native_frame") != frame.get("native_frame") or
                frame.get("video_frame") != index or
                type(row.get("emergency_call_documented")) is not bool or
                type(row.get("immediate_pursuit_documented")) is not bool or
                any(type(value) not in (int, float) or not math.isfinite(value) or
                    abs(value - t) > 1e-4 for value in
                    (row.get("time_s"), frame.get("time_s")))):
            raise ValueError("Original dispatch record/frame join differs")
    return {"source_kind": "original_dispatch_record",
            "document_sha256": document_hash, "records_sha256": sha(record_path),
            "frame_map_sha256": sha(frame_map_path),
            "emergency_call_frames": sum(r["emergency_call_documented"] for r in rows),
            "immediate_pursuit_frames": sum(r["immediate_pursuit_documented"] for r in rows),
            "authorized_emergency_vehicle_verified": False,
            "physical_legal_verdict": None}


def validate_acoustic_capability(report_path, source_audio_path):
    """Check provenance of a later qualified 500-foot assessment without adjudication."""
    report = json.loads(Path(report_path).read_text())
    required = {"method", "normal_conditions", "distance_ft", "observer",
                "source_audio_sha256", "audibility_assessment", "calibration_source"}
    if (not required <= set(report) or report["source_audio_sha256"] != sha(source_audio_path)
            or report["normal_conditions"] is not True or
            type(report["distance_ft"]) not in (int, float) or
            not math.isfinite(report["distance_ft"]) or report["distance_ft"] < 500 or
            report["audibility_assessment"] not in ("audible", "not_audible", "uncertain") or
            not all(isinstance(report[key], str) and report[key].strip()
                    for key in ("method", "observer", "calibration_source"))):
        raise ValueError("Qualified 500-foot acoustic source incomplete")
    return {"report_sha256": sha(report_path), "audio_sha256": sha(source_audio_path),
            "distance_ft": report["distance_ft"],
            "source_assessment": report["audibility_assessment"],
            "legal_equipment_conclusion": None}


def measure_with_original_sources(config_path, native_path, frame_map_path,
                                  dispatch_path, wav_path, audio_observations_path,
                                  dispatch_document_path):
    """Join independent sources to the measured Native motion without source repair."""
    from measure import measure, rows

    native = rows(native_path)
    if len(native) != FRAMES or any(
            row.get("source_kind") != "original_native" for row in native):
        raise ValueError("Original Native motion required for source-bound measurement")
    acoustic = validate_audio(wav_path, audio_observations_path, frame_map_path)
    dispatch = validate_dispatch(dispatch_path, frame_map_path,
                                 dispatch_document_path)
    for index, row in enumerate(native):
        if (type(row.get("siren_observed")) is not bool or
                row["siren_observed"] != acoustic["siren_audible_by_frame"][index]):
            raise ValueError("Native siren state differs from independent audio review")
    measured = measure(config_path, native_path, frame_map_path, dispatch_path)
    if (measured["documented_response_frames"] !=
            sum(bool(r.get("emergency_call_documented") or
                     r.get("immediate_pursuit_documented"))
                for r in rows(dispatch_path))):
        raise ValueError("Dispatch response source differs")
    measured["source_kind"] = "original_joined_sources"
    measured["independent_audio_sha256"] = acoustic["audio_sha256"]
    measured["audio_observations_sha256"] = acoustic["observations_sha256"]
    measured["dispatch_document_sha256"] = dispatch["document_sha256"]
    measured["dispatch_records_sha256"] = dispatch["records_sha256"]
    measured["audible_at_500_ft_verified"] = False
    measured["authorized_emergency_vehicle_verified"] = False
    measured["physical_legal_verdict"] = None
    return measured
