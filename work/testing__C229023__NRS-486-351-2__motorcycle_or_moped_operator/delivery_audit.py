"""Independently audit exact saved same-lane sources and original-only delivery."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent
PREFIX = ROOT.name + '__'
CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
SUFFIXES = {'same_lane_pass', 'different_lane_pass', 'consented_two_abreast',
            'unconsented_two_abreast', 'three_abreast'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def camera(path, expected):
    process = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate,codec_name',
         '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(process.stdout)['streams']
    require(len(streams) == 1, 'Camera source requires one decoded stream')
    stream = streams[0]
    require((stream['width'], stream['height']) == expected and
            stream['r_frame_rate'] == '20/1' and
            stream['codec_name'] == 'ffv1' and
            int(stream['nb_read_frames']) == 900,
            'Camera codec, dimensions, rate or decoded frame count differ')
    return sha(path)


def audit(attempt, case_id, require_original=False):
    attempt = Path(attempt).resolve()
    require(case_id.startswith(PREFIX) and case_id.removeprefix(PREFIX) in SUFFIXES,
            'Foreign exact case')
    config = json.loads((attempt / 'config.json').read_text())
    require(config['selected_case_id'] == case_id and config['duration_s'] == 45 and
            config['rate_hz'] == 20, 'Exact attempt identity or frame profile differs')
    original = (attempt / 'acquisition.json').is_file()
    if require_original and not original:
        raise ValueError('Diagnostic source cannot satisfy original Native delivery')
    if original:
        provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
        require(provenance.get('provenance_kind') == 'native' and
                provenance.get('diagnostic_fixture') is False,
                'Original Native provenance missing')
        acquisition = json.loads((attempt / 'acquisition.json').read_text())
    else:
        marker = json.loads((attempt / 'diagnostic-source-note.json').read_text())
        require(marker.get('source_kind') == 'synthetic_diagnostic_fixture' and
                marker.get('case_id') == case_id and
                marker.get('physical_truth_claimed') is False,
                'Synthetic source provenance differs')
        acquisition = {}
    names = ['same-lane-history.jsonl', 'same-lane-scene.json',
             'trace.jsonl', 'video_frames.jsonl',
             *[name + '.mkv' for name in CAMERAS]]
    seals = {}
    for name in names:
        path = attempt / name
        require(path.is_file() and not path.is_symlink(), 'Missing saved source: ' + name)
        seals[name] = sha(path)
        if original:
            require(acquisition.get(name, {}).get('kind') == 'original_native' and
                    acquisition[name].get('sha256') == seals[name],
                    'Original Native source seal differs: ' + name)
    history, trace, mapping = [rows(attempt / name) for name in
                               ('same-lane-history.jsonl', 'trace.jsonl',
                                'video_frames.jsonl')]
    require(len(history) == len(trace) == len(mapping) == 900,
            'Incomplete original actor, telemetry or camera frame history')
    frame_start = history[0]['frame']
    require([item['frame'] for item in history] == list(range(frame_start, frame_start + 900)),
            'Original frames are not consecutive')
    expected_roles = {'ego', 'other'} | ({'third'} if case_id.endswith('__three_abreast') else set())
    for actor_row, telemetry, camera_row in zip(history, trace, mapping):
        require(actor_row['frame'] == telemetry['frame'] == camera_row['carla_frame'] and
                abs(actor_row['time_s'] - telemetry['time_s']) < 1e-6 and
                abs(actor_row['time_s'] - camera_row['time_s']) < 1e-6,
                'Original actor, telemetry or camera time join differs')
        participants = actor_row['actors']
        require(set(participants) == expected_roles and
                len({item['actor_id'] for item in participants.values()}) == len(expected_roles),
                'Original participant identities differ')
        require(all(item.get('lane_id') is not None and
                    item.get('station_m') is not None and
                    item.get('lateral_m') is not None for item in participants.values()),
                'Original lane or body readback absent')
    scene = json.loads((attempt / 'same-lane-scene.json').read_text())
    require(scene['case_id'] == case_id and
            all(scene.get(key) for key in (
                'ego_classification_source_sha256',
                'other_classification_source_sha256',
                'driver_identity_source_sha256',
                'consent_source_sha256', 'subsection_3_source_sha256')),
            'Exact case or independent context source missing')
    require(scene['ego_vehicle_class'] == 'motorcycle' and
            scene['subsection_3_status'] in ('unresolved', 'reviewed'),
            'Vehicle class or subsection 3 status differs')
    cameras = {name: camera(attempt / (name + '.mkv'), dims)
               for name, dims in CAMERAS.items()}
    pixel_reviewed = False
    if original:
        review = json.loads((attempt / 'independent-pixel-review.json').read_text())
        require(review.get('case_id') == case_id and
                review.get('frame_map_sha256') == seals['video_frames.jsonl'] and
                review.get('camera_sha256') == cameras and
                review.get('status') == 'reviewed' and review.get('reviewer'),
                'Independent original four-view pixel review missing')
        pixel_reviewed = True
    result = json.loads((attempt / 'result.json').read_text())
    require(result.get('case_id') == case_id and
            result.get('diagnostic_fixture') is (not original),
            'Native result identity or provenance differs')
    complete = bool(original and result.get('maneuver_completed') is True and
                    result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met')
    return {'case_id': case_id, 'native_source': original,
            'all_participants': True, 'time_join': True,
            'full_video_decode': True, 'actual_pixels': pixel_reviewed,
            'physical_completion': complete, 'original_frames': 900,
            'source_sha256': seals, 'camera_sha256': cameras}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--require-original', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.require_original), sort_keys=True))


if __name__ == '__main__':
    main()
