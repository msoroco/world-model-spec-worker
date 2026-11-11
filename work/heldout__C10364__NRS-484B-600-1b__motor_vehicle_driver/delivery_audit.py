"""Independent source and closure audit for an exact C10364 alley delivery.

Diagnostic mode exercises source joins and full media decode on marked synthetic
attempts. It never reports physical acceptance. Native mode requires a sealed
capture, owner exit, complete original interval and observed body passage.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess


PREFIX = 'heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('config.json', 'participant_footprints.jsonl', 'ego_motion.jsonl',
           'trace.jsonl', 'video_frames.jsonl')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _camera(path, expected_frames):
    if not path.is_file():
        raise ValueError('Missing original camera source: ' + path.name)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams',
                            'v:0', '-show_entries', 'stream=nb_read_frames,width,height',
                            '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1 or int(streams[0].get('nb_read_frames', -1)) != expected_frames:
        raise ValueError('Original camera frame count differs: ' + path.name)
    full = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
                           '-f', 'null', '-'], capture_output=True, text=True)
    if full.returncode:
        raise ValueError('Original camera full decode failed: ' + path.name)
    return {'sha256': digest(path), 'frames': expected_frames,
            'width': int(streams[0]['width']), 'height': int(streams[0]['height'])}


def audit(case_id, attempt, *, report_path=None, diagnostic_fixture=False):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    report_path = Path(report_path) if report_path else root / 'analysis-report.json'
    result_path = root / 'result.json'
    report = json.loads(report_path.read_text())
    result = json.loads(result_path.read_text())
    if (not case_id.startswith(PREFIX) or config.get('selected_case_id') != case_id
            or report.get('case_id') != case_id or result.get('case_id') != case_id):
        raise ValueError('Exact delivery case identity differs')
    if result.get('physical_acceptance_claimed') is not False or result.get('legal_acceptance_claimed') is not False:
        raise ValueError('Saved result makes unsupported acceptance claim')
    observed = report['measurements']['alley_original_exposure']['value']
    result_observed = result['measured_values']['alley_original_exposure']
    if observed != result_observed:
        raise ValueError('Saved result and analysis measurement differ')
    source_hashes = observed['source_sha256']
    for name in SOURCES[1:]:
        if source_hashes.get(name) != digest(root / name):
            raise ValueError('Original source hash differs: ' + name)
    frame_map = rows(root / 'video_frames.jsonl')
    footprints = rows(root / 'participant_footprints.jsonl')
    motion = rows(root / 'ego_motion.jsonl')
    trace = rows(root / 'trace.jsonl')
    if len(frame_map) < 2 or not (len(frame_map) == len(footprints) == len(motion) == len(trace)):
        raise ValueError('Original participant/time join is incomplete')
    frame_ids = [row['carla_frame'] for row in frame_map]
    if (frame_ids != [row['frame'] for row in footprints]
            or frame_ids != [row['frame'] for row in motion]
            or frame_ids != [row['frame'] for row in trace]):
        raise ValueError('Original participant/time join differs')
    decoded = {name: _camera(root / (name + '.mkv'), len(frame_map)) for name in CAMERAS}
    if diagnostic_fixture:
        if not (root / 'fixture-provenance.json').is_file() or (root / 'capture-seal.json').exists():
            raise ValueError('Diagnostic audit needs an explicitly marked unsealed fixture')
        scope = 'synthetic diagnostic source and media audit only'
    else:
        seal_path = root / 'capture-seal.json'
        exit_path = root / 'native-exit.json'
        if not seal_path.is_file() or not exit_path.is_file():
            raise ValueError('Native capture closure or owner exit is unverified')
        seal = json.loads(seal_path.read_text())
        owner_exit = json.loads(exit_path.read_text())
        if (seal.get('provenance_kind') != 'native'
                or seal.get('restoration', {}).get('restored') is not True
                or owner_exit.get('event') != 'native_exit'
                or owner_exit.get('capture_seal_sha256') != digest(seal_path)):
            raise ValueError('Native capture closure or owner exit is unverified')
        if any(seal.get('sources', {}).get(name) != digest(root / name) for name in SOURCES):
            raise ValueError('Sealed original source hash differs')
        if len(frame_map) != int(config['duration_s'] * config['rate_hz']):
            raise ValueError('Native original duration is incomplete')
        if result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
            raise ValueError('Physical alley passage is unverified')
        scope = 'source-verified Native alley delivery; legal judgment separate'
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'scope': scope, 'report_sha256': digest(report_path),
            'result_sha256': digest(result_path), 'original_sha256':
            {name: digest(root / name) for name in SOURCES},
            'cameras': decoded, 'frames': len(frame_map),
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report')
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, report_path=args.report,
                           diagnostic_fixture=args.diagnostic_fixture), indent=2))


if __name__ == '__main__':
    main()
