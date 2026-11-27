"""Independently audit saved route sources and four complete videos."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from route_measure import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
DIMS = {'overview': (1920, 1080), 'approach': (1280, 720),
        'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(attempt: Path, case_id: str, diagnostic: bool = False) -> dict:
    attempt = attempt.resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    spec = json.loads(required(attempt, 'case-spec.json').read_text())
    if config.get('selected_case_id') != case_id or spec.get('case_id') != case_id:
        raise ValueError('selected truck-route route case identity differs')
    source = required(attempt, 'original-route-observations.json')
    receipt = json.loads(required(attempt, 'original-route-receipt.json').read_text())
    packet = json.loads(source.read_text())
    if (receipt.get('case_id') != case_id or packet.get('case_id') != case_id
            or receipt.get('source_sha256') != sha(source)
            or receipt.get('diagnostic_fixture') is not diagnostic
            or packet.get('diagnostic_fixture') is not diagnostic
            or receipt.get('fps') != 20):
        raise ValueError('route source receipt or provenance differs')
    measurement = measure(source)
    if (measurement['intervening_designation'] != spec['street_class'] or
            measurement['destination_truck_route_observed'] != (spec['route_use'] == 'through') or
            measurement['enroute_purpose_kind'] != spec['enroute_purpose']):
        raise ValueError('original route or enroute category differs from selected case')
    if spec['enroute_purpose'] != 'none' and not measurement['enroute_activity_observed']:
        raise ValueError('original required-enroute activity absent')
    mapping = rows(required(attempt, 'video_frames.jsonl'))
    trace = rows(required(attempt, 'trace.jsonl'))
    frames = packet['frames']
    if (len(frames) != receipt.get('frame_count') or len(mapping) != len(frames)
            or len(trace) != len(frames) or (not diagnostic and len(frames) != 900)):
        raise ValueError('original vehicle and four-video frame join differs')
    for index, (frame, mapped, native) in enumerate(zip(frames, mapping, trace)):
        if (mapped.get('video_frame') != index or mapped.get('carla_frame') != frame.get('frame')
                or mapped.get('native_frame') != frame.get('frame')
                or native.get('frame') != frame.get('frame')
                or abs(mapped.get('time_s', -1) - frame['time_s']) > 1e-4
                or abs(native.get('time_s', -1) - frame['time_s']) > 1e-4):
            raise ValueError('original route frame/time join differs')
        if (frame.get('road_id') is None or frame.get('observation_source') not in ('original_native_snapshot','synthetic_diagnostic')):
            raise ValueError('original road identity/source missing')
    if not diagnostic:
        reviewed = json.loads(required(attempt, 'reviewed-route.json').read_text())
        if (sha(attempt / 'reviewed-route.json') != packet.get('site_source_sha256') or
                reviewed.get('case_id') != case_id or
                reviewed.get('source_provenance', {}).get('kind') != 'original_reviewed_site'):
            raise ValueError('original reviewed site source seal differs')
        for item in reviewed.get('source_provenance', {}).get('files', []):
            document = required(attempt, 'reviewed-sources/' + item['path'])
            if sha(document) != item['sha256']:
                raise ValueError('original reviewed source document changed: ' + item['path'])
        pixel_review = json.loads(required(attempt, 'original-pixel-review.json').read_text())
        if (pixel_review.get('format') != 'worker-original-pixel-review' or
                pixel_review.get('case_id') != case_id or
                not pixel_review.get('reviewer') or
                pixel_review.get('frame_count') != 900 or
                set(pixel_review.get('camera_sha256', {})) != set(CAMERAS) or
                not isinstance(pixel_review.get('visible_vehicle_frames'), list) or
                not pixel_review['visible_vehicle_frames']):
            raise ValueError('independent original-pixel review incomplete')
        for frame_number in pixel_review['visible_vehicle_frames']:
            if type(frame_number) is not int or not 0 <= frame_number < 900:
                raise ValueError('original-pixel review frame index invalid')
        if spec['enroute_purpose'] != 'none':
            activity_frames = pixel_review.get('visible_activity_prop_frames')
            if not isinstance(activity_frames, list) or not activity_frames:
                raise ValueError('independent original activity-prop pixel review incomplete')
            for frame_number in activity_frames:
                if type(frame_number) is not int or not 0 <= frame_number < 900:
                    raise ValueError('original activity-prop pixel review frame invalid')
    media = {}
    for camera in CAMERAS:
        path = required(attempt, camera + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-count_frames', '-show_entries',
            'stream=nb_read_frames,codec_name,width,height,r_frame_rate,avg_frame_rate',
            '-of', 'json', str(path)], capture_output=True, text=True, timeout=60)
        if probe.returncode:
            raise ValueError('four-camera ffprobe failed: ' + camera)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or int(streams[0]['nb_read_frames']) != len(frames):
            raise ValueError('four-camera frame count differs: ' + camera)
        stream = streams[0]
        if not diagnostic and (stream.get('codec_name') != 'ffv1'
                or (stream.get('width'), stream.get('height')) != DIMS[camera]
                or stream.get('r_frame_rate') != '20/1'):
            raise ValueError('original video codec, size or rate differs: ' + camera)
        decoded = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-nostdin', '-i', str(path), '-f', 'null', '-'],
            capture_output=True, timeout=120)
        if decoded.returncode:
            raise ValueError('four-camera full decode failed: ' + camera)
        media[camera] = {'sha256': sha(path), 'frames': len(frames),
            'codec': stream.get('codec_name'), 'width': stream.get('width'),
            'height': stream.get('height')}
        if not diagnostic and pixel_review['camera_sha256'][camera] != media[camera]['sha256']:
            raise ValueError('original-pixel review video hash differs: ' + camera)
    return {'format': 'worker-independent-route-delivery', 'case_id': case_id,
        'passed': True, 'diagnostic_only': diagnostic, 'physical_acceptance': False,
        'legal_acceptance': False, 'frame_count': len(frames),
        'source_sha256': sha(source), 'measurement': measurement,
        'full_video_decode': media}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = audit(args.attempt, args.case_id, args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case_id, 'passed': True}))


if __name__ == '__main__':
    main()
