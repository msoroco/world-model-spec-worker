"""Independent original City-space delivery audit; CPU fixtures stay synthetic."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from city_space import CASES, measure_original
from source_packet import ASSIGNMENT, load_reviewed

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('original-city-space.jsonl', 'city-space-context.json',
           'camera-frame-map.jsonl', 'trace.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def full_decode(path, frames):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-count_frames', '-show_entries', 'stream=nb_read_frames',
                            '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
                           capture_output=True, text=True, check=True, timeout=120)
    if probe.stdout.strip() != str(frames):
        raise ValueError('full video frame count differs: ' + str(path))
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
                    '-f', 'null', '-'], capture_output=True, check=True, timeout=180)


def audit(attempt, processing_path, case_id, *, synthetic_fixture=False):
    attempt = Path(attempt).resolve()
    processing_path = Path(processing_path).resolve()
    case = next((c for c in CASES if ASSIGNMENT + '__' + c.name == case_id), None)
    if case is None:
        raise ValueError('unknown exact City-space case')
    provenance = read(attempt / 'acquisition-provenance.json')
    expected_kind = 'synthetic_fixture' if synthetic_fixture else 'native'
    if (provenance.get('provenance_kind') != expected_kind or
            provenance.get('diagnostic_fixture') is not synthetic_fixture):
        raise ValueError('exact original or explicit synthetic provenance required')
    seal = read(attempt / 'capture-seal.json')
    if (seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified'] or
            seal.get('restoration', {}).get('restored') is not True or
            seal.get('provenance_kind') != expected_kind):
        raise ValueError('sealed capture lifecycle incomplete')
    required = set(SOURCES) | {c + '.mkv' for c in CAMERAS}
    if not synthetic_fixture:
        required.add('reviewed-sources/city-space-packet.json')
    if not required <= set(seal.get('sources', {})):
        raise ValueError('sealed original City-space source inventory incomplete')
    for name, digest in seal['sources'].items():
        path = (attempt / name).resolve()
        if not path.is_relative_to(attempt) or not path.is_file() or sha(path) != digest:
            raise ValueError('sealed original missing or changed: ' + name)
    native = read(attempt / 'native-exit.json')
    owner = read(attempt / 'owner-release.json')
    if (native.get('event') != 'native_exit' or
            native.get('capture_seal_sha256') != sha(attempt / 'capture-seal.json') or
            owner.get('event') != 'owner_released' or
            owner.get('operator_attested') is not True or
            owner.get('native_exit_sha256') != sha(attempt / 'native-exit.json')):
        raise ValueError('Native exit and owner release not established')
    saved = read(processing_path)
    result_path = Path(saved.get('result', ''))
    if (saved.get('format') != 'worker-saved-processing' or
            saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id') != case_id or not saved.get('originals_preserved') or
            not result_path.is_file() or sha(result_path) != saved.get('result_sha256')):
        raise ValueError('saved-only result absent or changed')
    result = read(result_path)
    review = read(attempt / 'physical-visibility-review.json')
    if (result.get('case_id') != case_id or
            result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met' or
            result.get('maneuver_completed') is not True or
            review.get('physical_completion') is not True or
            not review.get('reviewer') or
            review.get('synthetic_fixture') is not synthetic_fixture):
        raise ValueError('parked physical completion and independent review missing')
    config = read(attempt / 'config.json')
    context = read(attempt / 'city-space-context.json')
    if (config.get('selected_case_id') != case_id or config.get('frame_count') != 900 or
            context.get('case_id') != case_id or context.get('scene', {}).get('cell_id') != 'C229439'):
        raise ValueError('City-space case or 900-frame construction differs')
    history, cameras, trace, frames = (lines(attempt / name) for name in
                                      ('original-city-space.jsonl', 'camera-frame-map.jsonl',
                                       'trace.jsonl', 'video_frames.jsonl'))
    count = 9 if synthetic_fixture else 900
    if any(len(rows) != count for rows in (history, cameras, trace, frames)):
        raise ValueError('complete original frame inventory missing')
    for index, (row, camera, point, frame) in enumerate(zip(history, cameras, trace, frames)):
        native_frame = row.get('original_frame')
        if (camera.get('frame_index') != index or camera.get('native_frame') != native_frame or
                camera.get('camera_frames') != {name: native_frame for name in CAMERAS} or
                point.get('frame') != native_frame or frame.get('carla_frame') != native_frame or
                frame.get('video_frame') != index or
                abs(row.get('time_s', -1) - frame.get('time_s', -2)) > .002):
            raise ValueError('original City-space and four-camera frame join differs')
    measured = measure_original(history, context['scene'], case,
                                diagnostic_frames=9 if synthetic_fixture else None)
    if (measured['all_footprints_overlap_governed_space'] is not case.inside_space or
            measured['city_vehicle'] is not case.city_vehicle or
            measured['council_designated'] is not case.designated or
            measured['official_posting'] is not case.posted):
        raise ValueError('original source conditions differ from exact case')
    if not synthetic_fixture:
        packet = attempt / 'reviewed-sources/city-space-packet.json'
        _, scene, _ = load_reviewed(packet, case_id)
        if scene != context['scene'] or sha(packet) != context.get('reviewed_packet_sha256'):
            raise ValueError('reviewed Council, posting or vehicle authority changed')
    for camera in CAMERAS:
        full_decode(attempt / (camera + '.mkv'), count)
    raw = Path(saved.get('analysis_directory', '')) / 'raw.mkv'
    if not raw.is_file():
        raise ValueError('saved synchronized video missing')
    full_decode(raw, count)
    needed = {'complete_vehicle', 'governed_space', 'official_device_face',
              'vehicle_status_source', 'council_designation_source'}
    if (review.get('video_sha256') != sha(raw) or
            review.get('frame_map_sha256') != sha(attempt / 'video_frames.jsonl') or
            not needed <= set(review.get('visible_and_reviewed', []))):
        raise ValueError('source-bound actual pixel review missing')
    return {'format': 'worker-delivery-audit', 'passed': True, 'case_id': case_id,
            'scope': 'synthetic CPU audit proof only' if synthetic_fixture else 'original Native delivery review',
            'cell_id': config['cell_id'], 'actor': config['actor'],
            'frame_count': count,
            'camera_contract_sha256': hashlib.sha256(json.dumps(config['cameras'], sort_keys=True).encode()).hexdigest(),
            'duration_s': config['duration_s'], 'candidate_id': config['candidate_id'],
            'city_location_kind': context['scene']['city_location_kind'],
            'governed_space_rect_m': context['scene']['governed_space_rect_m'],
            'measured': measured, 'source_sha256': {name: sha(attempt / name) for name in SOURCES},
            'video_sha256': sha(raw), 'saved_result_sha256': sha(result_path),
            'physical_completion_reviewed': True, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processing', required=True)
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.case), indent=2))
