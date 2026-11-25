"""Independent CPU check of saved C111329 sources and four encoded views.

Diagnostic mode checks software joins only. Original mode delegates to the
separate PNG and Native-seal audit and still leaves legal review unresolved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from delivery_audit import CASES, audit_delivery
from native_observation import CAMERAS, CAMERA_DIMENSIONS, analyze_saved
from site_geometry import assess_site


def _sha(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _rows(root: Path, name: str):
    return [json.loads(line) for line in _required(root, name).read_text().splitlines() if line]


def _decode(path: Path, expected: tuple[int, int], frames: int):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries",
        "stream=width,height,nb_read_frames,avg_frame_rate", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=180)
    streams = json.loads(probe.stdout)["streams"]
    if len(streams) != 1:
        raise ValueError("camera stream count differs: " + path.name)
    stream = streams[0]
    if (stream["width"], stream["height"]) != tuple(expected) or \
       stream.get("avg_frame_rate") != "20/1" or \
       int(stream["nb_read_frames"]) != frames:
        raise ValueError("camera frame profile differs: " + path.name)
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-f", "null", "-"], check=True,
        capture_output=True, timeout=180)
    return _sha(path)


def inspect(attempt: Path, case_id: str, *, diagnostic: bool) -> dict:
    attempt = Path(attempt).resolve()
    if case_id not in CASES:
        raise ValueError("unknown exact selected case")
    packet_path = _required(attempt, "effective-site-packet.json")
    observation_path = _required(attempt, "original-site-observation.json")
    packet = json.loads(packet_path.read_text())
    observation = json.loads(observation_path.read_text())
    if observation.get("case_id") != case_id:
        raise ValueError("exact original observation case differs")
    site = assess_site(packet, require_operating=False)
    receipt = {"path": str(observation_path), "sha256": _sha(observation_path),
               "frame_count": observation["frame_count"], "case_id": case_id}
    if diagnostic:
        provenance = json.loads(_required(attempt, "acquisition-provenance.json").read_text())
        if provenance.get("diagnostic_fixture") is not True or \
           provenance.get("provenance_kind") != "synthetic_fixture":
            raise ValueError("diagnostic fixture provenance required")
        motion = analyze_saved(packet, receipt, expected_case_id=case_id, required_frames=900)
        frame_map, trace = _rows(attempt, "video_frames.jsonl"), _rows(attempt, "trace.jsonl")
        if len(frame_map) != 900 or len(trace) != 900:
            raise ValueError("original diagnostic frame join count differs")
        for index, (observed, mapped, body) in enumerate(zip(observation["frames"], frame_map, trace)):
            if mapped.get("video_frame") != index or \
               mapped.get("carla_frame") != observed["frame"] or \
               mapped.get("native_frame") != observed["frame"] or \
               body.get("frame") != observed["frame"] or \
               abs(mapped.get("time_s", -1) - observed["time_s"]) > 1e-6 or \
               abs(body.get("time_s", -1) - observed["time_s"]) > 1e-6 or \
               body.get("position_m") != observed["walker_xyz_m"]:
                raise ValueError("original diagnostic frame/time/body join differs")
        camera_hashes = {name: _decode(_required(attempt, name + ".mkv"),
            CAMERA_DIMENSIONS[name], 900) for name in CAMERAS}
        if site["marked_crosswalk_present"] is not CASES[case_id][0] or \
           motion["both_devices_operating_during_crossing"] is not CASES[case_id][1]:
            raise ValueError("diagnostic exact case distinction differs")
        return {"format": "worker-independent-cpu-delivery", "case_id": case_id,
            "diagnostic_fixture": True, "source_site_sha256": _sha(packet_path),
            "source_observation_sha256": _sha(observation_path),
            "camera_source_sha256": camera_hashes,
            "frame_count": 900, "full_encoded_camera_decodes": 4,
            "exact_case_measurement": {"marked": site["marked_crosswalk_present"],
                "both_devices_operating_during_crossing": motion["both_devices_operating_during_crossing"]},
            "physical_acceptance": False, "legal_verdict": None}
    provenance = json.loads(_required(attempt, "native-provenance.json").read_text())
    result = audit_delivery(packet, receipt, case_id=case_id,
                            native_provenance=provenance)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = inspect(args.attempt, args.case_id, diagnostic=args.diagnostic)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": args.case_id, "diagnostic_fixture": args.diagnostic,
                      "frame_count": result["frame_count"], "physical_acceptance": False}))


if __name__ == "__main__":
    main()
