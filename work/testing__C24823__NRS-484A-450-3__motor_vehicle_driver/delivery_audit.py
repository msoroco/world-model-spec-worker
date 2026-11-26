"""Independent exact-case original yield source, time and four-video audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from yield_site import ASSIGNMENT as ASSIGNMENT_ID
from yield_source import SUFFIXES
from yield_measure import measure
from yield_source import CAMERAS, DIMENSIONS


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def decode(path, dimensions, count):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
        "-of", "json", str(path)], capture_output=True, text=True, check=True, timeout=180)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or (streams[0].get("width"), streams[0].get("height")) != tuple(dimensions) or (
            int(streams[0].get("nb_read_frames", -1)) != count or
            streams[0].get("avg_frame_rate") != "20/1"):
        raise ValueError("original camera profile or count differs: " + path.name)
    process = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(path),
        "-map", "0:v:0", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    if process.returncode:
        raise ValueError("original camera full decode failed: " + path.name + " " + process.stderr[-200:])
    return {"sha256": sha(path), "decoded_frames": count,
            "dimensions": list(dimensions), "fps": 20}


def audit(attempt, case_id, *, diagnostic=False):
    attempt = Path(attempt).resolve()
    if case_id not in {ASSIGNMENT_ID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact yield delivery case")
    map_path = required(attempt, "original-yield-site.json")
    trace_path = required(attempt, "original-yield-trace.jsonl")
    receipt_path = required(attempt, "original-yield-receipt.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("case_id") != case_id or bool(receipt.get("diagnostic_fixture")) != diagnostic:
        raise ValueError("original source provenance or exact case differs")
    if diagnostic:
        provenance = json.loads(required(attempt, "fixture-provenance.json").read_text(encoding="utf-8"))
        if provenance.get("case_id") != case_id or "CPU diagnostic only" not in provenance.get("scope", ""):
            raise ValueError("explicit exact diagnostic provenance required")
    elif receipt.get("frame_count") != 900 or not receipt.get("camera_capture_complete"):
        raise ValueError("full original four-camera Native yield capture required")
    if not diagnostic:
        site = json.loads(map_path.read_text(encoding="utf-8"))
        if site.get("source_review_status") != "reviewed_original":
            raise ValueError("reviewed original yield site required")
        seal = json.loads(required(attempt, "native-seal.json").read_text(encoding="utf-8"))
        if (seal.get("case_id") != case_id or seal.get("frame_count") != 900 or
                seal.get("site_sha256") != sha(map_path) or
                seal.get("trace_sha256") != sha(trace_path) or
                seal.get("restored") is not True):
            raise ValueError("original Native completion or source seal differs")
    motion = measure(attempt, case_id)
    original = rows(trace_path)
    mapping = rows(required(attempt, "video_frames.jsonl"))
    graph = rows(required(attempt, "trace.jsonl"))
    if not original or len(original) != len(mapping) or len(original) != len(graph):
        raise ValueError("original source/frame/graph counts differ")
    for index, (body, mapped, sampled) in enumerate(zip(original, mapping, graph)):
        if (mapped.get("video_frame") != index or mapped.get("carla_frame") != body["frame"] or
                mapped.get("native_frame") != body["frame"] or sampled.get("frame") != body["frame"] or
                abs(mapped.get("time_s", -1) - body["time_s"]) > 1e-4):
            raise ValueError("original source/frame/time join differs")
    videos = {name: decode(required(attempt, name + ".mkv"), DIMENSIONS[name], len(original))
              for name in CAMERAS}
    png_sources = {}
    if not diagnostic:
        if set(receipt.get("camera_sources", {})) != set(CAMERAS):
            raise ValueError("all original camera source archives required")
        for name in CAMERAS:
            spec = receipt["camera_sources"][name]
            source = required(attempt, spec["path"])
            if sha(source) != spec.get("sha256") or spec.get("frame_count") != 900:
                raise ValueError("original camera source archive changed: " + name)
            with ZipFile(source) as archive:
                expected = [f"{row['frame']:08d}.png" for row in original]
                if archive.namelist() != expected:
                    raise ValueError("original camera source frame order differs: " + name)
                for row, member in zip(original, expected):
                    pixels = archive.read(member)
                    if row.get("camera_frames", {}).get(name) != {
                            "member": member, "sha256": hashlib.sha256(pixels).hexdigest()}:
                        raise ValueError("original camera pixel source changed: " + name)
            png_sources[name] = sha(source)
    return {"format": "worker-independent-yield-delivery-audit",
        "case_id": case_id, "diagnostic_fixture": diagnostic,
        "site_sha256": sha(map_path), "trace_sha256": sha(trace_path),
        "receipt_sha256": sha(receipt_path), "frame_count": len(original),
        "decoded_images": len(original) * 4, "full_encoded_camera_decodes": 4,
        "videos": videos, "original_png_archives_sha256": png_sources,
        "reference_kind": motion["reference"]["reference_kind"],
        "stop_sample_count": len(motion["original_stop_samples"]),
        "original_driver_view": "unverified", "actual_pixels_verified": False,
        "physical_acceptance": False, "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("refusing to overwrite independent audit receipt")
    result = audit(args.attempt, args.case_id, diagnostic=args.diagnostic)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case_id": args.case_id, "frame_count": result["frame_count"],
                      "diagnostic_fixture": args.diagnostic, "physical_acceptance": False}))


if __name__ == "__main__":
    main()
