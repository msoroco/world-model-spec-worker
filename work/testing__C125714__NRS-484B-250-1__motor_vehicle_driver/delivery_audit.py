"""Independent source and comparison audit for saved C125714 attempts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

from analysis import build_report
from crossing_audit import audit_comparison


CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")
REVIEW_SOURCES = {name: "context_sources/" + name + ".bin" for name in
                  ("public_access_source", "device_inventory_source", "driver_scope_source")}
ORIGINALS = ("trace.jsonl", "video_frames.jsonl", "road.xodr", "carla_recorder.log",
             "reviewed-context.json", "intersection-context.json",
             "ego-body-history.jsonl", "other-body-history.jsonl",
             "controller-history.jsonl", *REVIEW_SOURCES.values(), *CAMERAS)
CAMERA_SIZE = {"overview.mkv": (1920, 1080), "approach.mkv": (1280, 720),
               "reference_corner.mkv": (1280, 720), "driver_reference.mkv": (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text())


def audit_reviewed_context(path):
    """Recheck the retained site packet against original map and scene context."""
    path = Path(path)
    packet = _read(path / "reviewed-context.json")
    context = _read(path / "intersection-context.json")
    provenance = _read(path / "acquisition-provenance.json")
    if (provenance.get("reviewed_context_sha256") != sha(path / "reviewed-context.json") or
            context.get("reviewed_context_sha256") != sha(path / "reviewed-context.json")):
        raise ValueError("reviewed context provenance differs from retained packet")
    if (context.get("crossing") != packet.get("crossing") or
            context.get("law_context") != packet.get("law_context")):
        raise ValueError("reviewed crossing or law context differs from original scene")
    law = packet["law_context"]
    if law.get("map_source") != sha(path / "road.xodr"):
        raise ValueError("reviewed map differs from original OpenDRIVE")
    if (law.get("public_access") is not True or law.get("human_driver") is not True or
            law.get("devices") != [] or
            not all(law.get(key) for key in ("public_access_source",
                                             "device_inventory_source",
                                             "driver_scope_source"))):
        raise ValueError("reviewed public-highway, driver or device context incomplete")
    if (law.get("approach_relation") == "crossing" and
            law.get("ego_highway") == law.get("other_highway")):
        raise ValueError("reviewed crossing lacks distinct highway identities")
    for key, retained in REVIEW_SOURCES.items():
        descriptor = law.get(key)
        source = path / retained
        if (not isinstance(descriptor, dict) or not descriptor.get("reviewer") or
                not descriptor.get("source_citation") or
                not source.is_file() or descriptor.get("source_sha256") != sha(source)):
            raise ValueError("reviewed " + key + " original bytes or provenance differ")
    return {"reviewed_context_sha256": sha(path / "reviewed-context.json"),
            "original_map_sha256": sha(path / "road.xodr"),
            "review_source_hashes": {key: sha(path / name)
                                     for key, name in REVIEW_SOURCES.items()}}


def audit_media_time(path, expected_frames):
    """Decode every original camera and join its count to original frame IDs."""
    path = Path(path)
    if type(expected_frames) is not int or expected_frames <= 0:
        raise ValueError("sealed original frame count missing")
    def rows(name):
        values = [json.loads(line) for line in (path / name).read_text().splitlines()
                  if line.strip()]
        if len(values) != expected_frames:
            raise ValueError("original frame count differs: " + name)
        return values
    frame_map = rows("video_frames.jsonl")
    native_frames = [row["native_frame"] for row in frame_map]
    times = [row.get("time_s") for row in frame_map]
    if ([row["video_frame"] for row in frame_map] != list(range(expected_frames)) or
            any(type(frame) is not int for frame in native_frames) or
            any(b != a + 1 for a, b in zip(native_frames, native_frames[1:])) or
            any(type(t) not in (int, float) or not math.isfinite(t) for t in times) or
            any(abs((b - a) - .05) > 1e-4 for a, b in zip(times, times[1:]))):
        raise ValueError("original video frame map is not contiguous at 20 Hz")
    for name in ("trace.jsonl", "ego-body-history.jsonl", "other-body-history.jsonl",
                 "controller-history.jsonl"):
        source_rows = rows(name)
        if [row["frame"] for row in source_rows] != native_frames:
            raise ValueError("original time join differs: " + name)
        if any(type(row.get("time_s")) not in (int, float) or
               not math.isfinite(row["time_s"]) or
               abs(row["time_s"] - timestamp) > 1e-4
               for row, timestamp in zip(source_rows, times)):
            raise ValueError("original timestamp join differs: " + name)
    counts = {}
    for name, dimensions in CAMERA_SIZE.items():
        video = path / name
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-count_frames", "-show_entries",
                                "stream=width,height,codec_name,avg_frame_rate,nb_read_frames",
                                "-of", "json", str(video)],
                               capture_output=True, text=True, timeout=180)
        if probe.returncode:
            raise ValueError("original camera probe failed: " + name)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1:
            raise ValueError("original camera stream count differs: " + name)
        stream = streams[0]
        if ((stream.get("width"), stream.get("height")) != dimensions or
                int(stream.get("nb_read_frames", -1)) != expected_frames):
            raise ValueError("original camera dimensions or frame count differ: " + name)
        if stream.get("codec_name") != "ffv1" or stream.get("avg_frame_rate") != "20/1":
            raise ValueError("original camera FFV1 or 20 Hz contract differs: " + name)
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video),
                                  "-f", "null", "-"], capture_output=True, timeout=180)
        if decoded.returncode:
            raise ValueError("original camera full decode failed: " + name)
        counts[name] = expected_frames
    return counts


def audit_attempt(path, *, diagnostic=False):
    """Verify original closure and source binding before using measurements."""
    path = Path(path)
    seal = _read(path / "capture-seal.json")
    exit_receipt = _read(path / "native-exit.json")
    provenance = _read(path / "acquisition-provenance.json")
    if diagnostic:
        if provenance.get("provenance_kind") != "synthetic_fixture" or provenance.get("diagnostic_fixture") is not True:
            raise ValueError("explicit synthetic diagnostic provenance required")
    elif provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
        raise ValueError("original Native acquisition required")
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
            seal.get("restoration", {}).get("restored") is not True):
        raise ValueError("Native closure sequence or restoration unverified")
    if any(seal.get("encoder_exit_codes", {}).get(name.removesuffix(".mkv")) != 0
           for name in CAMERAS):
        raise ValueError("four camera encoder exits unverified")
    if (exit_receipt.get("event") != "native_exit" or
            exit_receipt.get("capture_seal_sha256") != sha(path / "capture-seal.json") or
            exit_receipt.get("native_process_exit_code") != 0 or
            exit_receipt.get("capture_command_failed") is not False):
        raise ValueError("Native exit does not bind a successful sealed capture")
    acquisition = _read(path / "acquisition.json")
    for name in ORIGINALS:
        source = path / name
        if (not source.is_file() or acquisition.get(name, {}).get("kind") != "original_native" or
                acquisition[name].get("sha256") != sha(source) or
                seal.get("sources", {}).get(name) != sha(source)):
            raise ValueError("original source missing or changed: " + name)
    site_review = audit_reviewed_context(path)
    decoded_frames = {} if diagnostic else audit_media_time(path, seal.get("frames"))
    report = build_report(path)
    measurement = report["measurements"]["crossing_entry_measurement"]["value"]
    if measurement["legal_judgment"] != "unresolved":
        raise ValueError("legal judgment must remain unresolved in physical audit")
    return {"source_hashes": {name: sha(path / name) for name in ORIGINALS},
            "site_review": site_review,
            "decoded_frames": decoded_frames,
            "diagnostic_fixture": diagnostic,
            "measurements": measurement, "legal_verdict_claimed": False,
            "physical_acceptance_claimed": False}


def audit_pair(left, right, declared_differences, *, diagnostic=False):
    """Require two independently sealed attempts and one realized variable."""
    left_audit = audit_attempt(left, diagnostic=diagnostic)
    right_audit = audit_attempt(right, diagnostic=diagnostic)
    def trace(path):
        path = Path(path)
        context = _read(path / "intersection-context.json")
        samples = {}
        for party in ("ego", "other"):
            samples[party + "_samples"] = [json.loads(line) for line in
                (path / (party + "-body-history.jsonl")).read_text().splitlines() if line.strip()]
        return {"context": context["law_context"], "crossing": context["crossing"],
                **samples}
    comparison = audit_comparison(trace(left), trace(right), declared_differences)
    return {"left": left_audit, "right": right_audit,
            "comparison": comparison, "legal_verdict_claimed": False}
