"""Validate independently acquired siren and dispatch evidence for C109028.

The actuator request is never an observation. This module joins a microphone
recording, reviewed per-frame audio observations, and original dispatch records.
An audio observation is a documented human/source review, not a CARLA flag or
an automatic legal conclusion. The 500-foot equipment-capability question stays
unknown until a qualified normal-condition acoustic test is supplied.
"""
from __future__ import annotations

import hashlib
import base64
import json
import math
import wave
import zlib
from array import array
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


def validate_pcm_source(source_path):
    """Validate retained 30 s PCM, either a WAV or lossless textual PCM envelope."""
    source_path = Path(source_path)
    if not source_path.is_file():
        raise ValueError("Missing original microphone recording")
    if source_path.suffix == ".wav":
        with wave.open(str(source_path), "rb") as stream:
            channels, width, rate, samples = (stream.getnchannels(),
                                               stream.getsampwidth(),
                                               stream.getframerate(),
                                               stream.getnframes())
            raw = stream.readframes(samples)
        if (channels, width, rate, samples) != (1, 2, 48000, 48000 * WINDOW_S):
            raise ValueError("Microphone WAV must be 30 s mono PCM16 at 48 kHz")
        return sha(source_path), raw
    source = json.loads(source_path.read_text())
    if (source.get("format") != "c109028-pcm16-zlib-base64-v1" or
            source.get("rate_hz") != 48000 or source.get("channels") != 1 or
            source.get("sample_width_bytes") != 2 or
            source.get("samples") != 48000 * WINDOW_S or
            source.get("source_kind") != "independent_microphone_pcm"):
        raise ValueError("Microphone PCM source metadata incomplete")
    try:
        compressed = base64.b64decode(source["payload"], validate=True)
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, int(48000 * WINDOW_S * 2 + 1))
    except (KeyError, ValueError, zlib.error) as exc:
        raise ValueError("Microphone PCM source payload invalid") from exc
    if (len(raw) != 48000 * WINDOW_S * 2 or not decoder.eof or
            decoder.unused_data or decoder.unconsumed_tail or
            hashlib.sha256(raw).hexdigest() != source.get("pcm_sha256")):
        raise ValueError("Microphone PCM source length/hash differs")
    return sha(source_path), raw


def validate_audio(wav_path, observations_path, frame_map_path):
    """Check original microphone bytes and reviewed observations against Native time."""
    wav_path, observations_path = Path(wav_path), Path(observations_path)
    audio_hash, pcm = validate_pcm_source(wav_path)
    samples = array("h")
    samples.frombytes(pcm)
    if len(samples) != FRAMES * 2400:
        raise ValueError("Microphone frame/sample count differs")
    rows, mapping = read_rows(observations_path), read_rows(frame_map_path)
    observed = []
    for index, (row, frame) in enumerate(zip(rows, mapping)):
        t = frame.get("time_s")
        if (row.get("source_kind") != "independent_microphone_review" or
                row.get("audio_sha256") != audio_hash or
                row.get("native_frame") != frame.get("native_frame") or
                frame.get("video_frame") != index or
                type(row.get("siren_audible")) is not bool or
                not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip() or
                type(t) not in (int, float) or not math.isfinite(t) or
                type(row.get("time_s")) not in (int, float) or
                not math.isfinite(row["time_s"]) or
                abs(row["time_s"] - t) > .003):
            raise ValueError("Independent audio observation/frame join differs")
        if row["siren_audible"] and max(abs(v) for v in samples[
                index * 2400:(index + 1) * 2400]) < 100:
            raise ValueError("Reviewed audible siren lacks microphone signal energy")
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
        t = frame.get("time_s")
        if (row.get("source_kind") != "original_dispatch_record" or
                row.get("document_sha256") != document_hash or
                row.get("native_frame") != frame.get("native_frame") or
                frame.get("video_frame") != index or
                type(row.get("emergency_call_documented")) is not bool or
                type(row.get("immediate_pursuit_documented")) is not bool or
                type(t) not in (int, float) or not math.isfinite(t) or
                type(row.get("time_s")) not in (int, float) or
                not math.isfinite(row["time_s"]) or
                abs(row["time_s"] - t) > .003):
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
