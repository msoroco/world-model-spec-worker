"""Independent saved-source audit for through-highway cases.

This checks a sealed original-frame packet. Physical visibility and legal review
remain local acceptance tasks; fixture bytes do not prove either one.
"""

import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from finalize_saved import finalize
from original_runner import REQUIRED

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def check_file(ref, reason):
    path = Path(ref.get("path", ""))
    require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == ref.get("sha256"), reason)


def audit_saved(source, measured):
    require(source.get("case_id") == measured.get("case_id"), "exact case binding mismatch")
    require(source.get("map_sha256") == measured.get("map_sha256") and source.get("intersection_id") == measured.get("intersection_id"), "map or intersection source mismatch")
    check_file(source.get("native_result", {}), "sealed Native result mismatch")
    for name in ("municipal_jurisdiction", "through_highway_designation", "entrance_control", "antecedent_review"):
        check_file(source.get(name, {}), f"{name} source seal mismatch")
    frame_map = source.get("frame_map")
    count = measured.get("original_frame_count")
    require(isinstance(count, int) and count >= 400 and isinstance(frame_map, list) and len(frame_map) == count, "complete original frame map missing")
    first_native = frame_map[0].get("native_frame")
    require(type(first_native) is int, "original Native frame identity missing")
    for i, row in enumerate(frame_map):
        require(row.get("frame_index") == i and row.get("native_frame") == first_native + i
                and isinstance(row.get("time_s"), (int, float)) and abs(row["time_s"] - i / 20) <= 0.002,
                "original frame/time join failed")
    samples = measured.get("original_samples")
    require(isinstance(samples, list) and len(samples) == count, "measured original history missing")
    for i, row in enumerate(samples):
        require(row.get("frame_index") == i and row.get("native_frame") == frame_map[i]["native_frame"]
                and abs(row.get("time_s", -1) - frame_map[i]["time_s"]) <= 0.002,
                "measurement frame/time join failed")
        require(all(row.get(role, {}).get("center_xy") is not None for role in ("through", "entering")),
                "both actor histories missing")
    cameras = source.get("cameras", {})
    require(set(cameras) == set(CAMERAS), "four camera sources missing")
    for name in CAMERAS:
        camera = cameras[name]
        check_file(camera, f"{name} camera seal mismatch")
        require(camera.get("decoded_frames") == count and camera.get("original_frame_first") == 0
                and camera.get("original_frame_last") == count - 1, f"{name} full decode/frame join missing")
    require(source.get("physical_completion") is True, "physical completion receipt missing")
    return {"format": "worker-through-highway-saved-audit", "case_id": source["case_id"],
            "original_frame_count": count, "source_seals_checked": True,
            "physical_visibility": "requires_review", "legal_status": "unresolved"}


def audit_comparison(left_source, left_measured, right_source, right_measured):
    left = audit_saved(left_source, left_measured)
    right = audit_saved(right_source, right_measured)
    require(left_measured.get("entering_maneuver") == right_measured.get("entering_maneuver")
            and left_measured.get("intersection_id") == right_measured.get("intersection_id")
            and left_measured.get("map_sha256") == right_measured.get("map_sha256"),
            "comparison fixed conditions changed")
    require(left_measured.get("through_request") == "yield_request"
            and right_measured.get("through_request") == "continue_request", "comparison requested difference missing")
    return {"case_ids": [left["case_id"], right["case_id"]],
            "original_frame_counts": [left["original_frame_count"], right["original_frame_count"]],
            "legal_status": "unresolved"}


def decode_camera(path, size):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-count_frames', '-show_entries',
                            'stream=nb_read_frames,width,height,r_frame_rate',
                            '-of', 'json', str(path)], capture_output=True, text=True,
                           check=True, timeout=120)
    streams = json.loads(probe.stdout).get('streams', [])
    require(len(streams) == 1, 'one original camera stream required')
    stream = streams[0]
    require(stream.get('nb_read_frames') == '900' and stream.get('r_frame_rate') in ('20/1', '20')
            and [stream.get('width'), stream.get('height')] == size,
            'original camera profile or frame count changed')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'],
                   capture_output=True, check=True, timeout=180)
    return {'decoded_frames': 900, 'size': size}


def audit_attempt(attempt, processed, case_id):
    attempt, processed = Path(attempt), Path(processed)
    require(attempt.is_dir() and not attempt.is_symlink(), 'original attempt missing')
    seal_path = attempt / 'capture-seal.json'
    require(seal_path.is_file() and not seal_path.is_symlink(), 'original capture seal missing')
    seal = json.loads(seal_path.read_text())
    require(seal.get('case_id') == case_id and seal.get('provenance_kind') == 'native'
            and seal.get('diagnostic_fixture') is False and seal.get('frames') == 900,
            'original capture identity missing')
    for relative, digest in seal.get('sources', {}).items():
        part = Path(relative)
        path = attempt / part
        require(not part.is_absolute() and '..' not in part.parts and path.is_file()
                and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                'original sealed source changed: ' + relative)
    reviewed_manifest = json.loads((attempt / 'reviewed-site/source-manifest.json').read_text())
    require(reviewed_manifest.get('native_adapter_sha256') == hashlib.sha256(
        (attempt / 'reviewed-site/native-adapter.py').read_bytes()).hexdigest(),
        'original Native adapter source changed')
    fixed_sources = {name: reviewed_manifest['sources'][name]['sha256'] for name in REQUIRED}
    fixed_sources['native_adapter.py'] = reviewed_manifest['native_adapter_sha256']
    config = json.loads((attempt / 'config.json').read_text())
    with tempfile.TemporaryDirectory() as temporary:
        measured = finalize(attempt, case_id, Path(temporary) / 'measurement.json')['measurement']
        frame_map = [json.loads(line) for line in (attempt / 'camera-frame-map.jsonl').read_text().splitlines()]
        video_map = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
        require(len(frame_map) == len(video_map) == 900, 'original camera/Native frame count differs')
        for index, (sample, frame, video) in enumerate(zip(measured['original_samples'], frame_map, video_map)):
            native = sample['native_frame']
            require(frame.get('frame_index') == index and frame.get('native_frame') == native
                    and frame.get('camera_frames') == {name: native for name in CAMERAS}
                    and video.get('video_frame') == index and video.get('carla_frame') == native
                    and video.get('native_frame') == native and video.get('time_s') == sample['time_s']
                    and frame.get('time_s') == sample['time_s'],
                    'original four-camera/Native same-tick join differs')
        decoded = {}
        for name in CAMERAS:
            decoded[name] = decode_camera(attempt / (name + '.mkv'),
                                          [1920, 1080] if name == 'overview' else [1280, 720])
        require(processed.is_file() and not processed.is_symlink(), 'processed original physical result missing')
        physical = json.loads(processed.read_text())
        require(physical.get('case_id') == case_id and physical.get('provenance_kind') == 'native'
                and physical.get('diagnostic_fixture') is False
                and physical.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met',
                'original physical completion missing')
        return {'format': 'c179789-original-delivery-audit-v1', 'case_id': case_id,
                'capture_seal_sha256': hashlib.sha256(seal_path.read_bytes()).hexdigest(),
                'processed_result_sha256': hashlib.sha256(processed.read_bytes()).hexdigest(),
                'frame_count': 900, 'camera_decodes': decoded,
                'map_sha256': measured['map_sha256'], 'intersection_id': measured['intersection_id'],
                'entering_maneuver': measured['entering_maneuver'],
                'through_request': measured['through_request'],
                'engineering_request': {key: config['case'].get(key) for key in
                    ('antecedent_pause_s', 'through_approach_speed_mps')},
                'fixed_sources': fixed_sources,
                'through_highway_measurement': {key: measured[key] for key in
                    ('first_conflict_frame', 'entering_preentry_min_speed_mps',
                     'entering_preentry_pause_s', 'through_preentry_min_speed_mps')},
                'physical_completion': True, 'physical_visibility': 'requires_review',
                'antecedent_legal_review': 'unresolved', 'right_of_way_legal_review': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processed', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior original audit')
    args.output.write_text(json.dumps(audit_attempt(args.attempt, args.processed, args.case), indent=2) + '\n')


if __name__ == '__main__':
    main()
