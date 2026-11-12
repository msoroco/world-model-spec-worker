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
import sys


PREFIX = 'heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('config.json', 'participant_footprints.jsonl', 'ego_motion.jsonl',
           'trace.jsonl', 'video_frames.jsonl')

# The exported runtime owns the full-frame decoder and exact-file receipt format.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
from scenario_pipeline.worker_exchange import media


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


def _visibility(root, case_id, frame_count, cameras):
    path = root / 'participant-visibility-review.json'
    if not path.is_file():
        raise ValueError('Independent participant pixel visibility review is missing')
    review = json.loads(path.read_text())
    if review.get('case_id') != case_id or not review.get('reviewer'):
        raise ValueError('Participant visibility review identity is incomplete')
    marks = review.get('visible_participants', {})
    for participant in ('ego', 'pedestrian', 'property'):
        mark = marks.get(participant, {})
        camera = mark.get('camera')
        frame = mark.get('video_frame')
        if (camera not in cameras or mark.get('camera_sha256') != cameras[camera]['sha256']
                or not isinstance(frame, int) or not 0 <= frame < frame_count
                or mark.get('visible') is not True):
            raise ValueError('Participant pixel visibility is unverified: ' + participant)
    return {'path': path.name, 'sha256': digest(path), 'reviewer': review['reviewer']}


def verify_native_alley_sources(root, config, case_id):
    original_survey = (root / 'alley-survey-original.json').read_bytes()
    survey = json.loads(original_survey)
    verification = json.loads((root / 'alley-survey-verification.json').read_text())
    if (survey.get('format') != 'worker-native-alley-survey-v1' or
            survey.get('verified_alley') is not True or
            survey.get('map_name') != verification.get('map_name') or
            survey.get('opendrive_sha256') != verification.get('opendrive_sha256') or
            survey.get('polygon_xy') != verification.get('polygon_xy') or
            survey.get('alley_width_m') != verification.get('alley_width_m') or
            survey.get('routes', {}).get(verification.get('selected_direction')) !=
            verification.get('selected_route') or
            verification.get('selected_direction') != config.get('alley_direction') or
            verification.get('verified') is not True or
            verification.get('operator_manifest_sha256') != sha256(original_survey).hexdigest() or
            not survey.get('reviewer') or not survey.get('evidence_reference')):
        raise ValueError('Original Native alley survey is absent or differs')
    probe = json.loads((root / 'construction-probe.json').read_text())
    route = probe.get('route', {})
    selected_route = verification['selected_route']
    if (probe.get('case_id') != case_id or
            probe.get('native_survey') != verification or
            route.get('map_name') != verification['map_name'] or
            route.get('road_id') != selected_route['road_id'] or
            route.get('lane_id') != selected_route['lane_id'] or
            abs(route.get('start_s', float('inf')) - selected_route['start_s']) > .1 or
            route.get('polygon_source_sha256') != verification['operator_manifest_sha256']):
        raise ValueError('Native alley route differs from reviewed survey')
    return verification


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
    primary = root / 'raw.mkv'
    if not primary.is_file():
        raise ValueError('Composed original source video is missing')
    receipt_path = root / 'source-decode-receipt.json'
    decode = media.audit(primary, len(frame_map), mapping_sha256=digest(root / 'video_frames.jsonl'),
                         receipt=receipt_path)
    visibility = None
    if diagnostic_fixture:
        if not (root / 'fixture-provenance.json').is_file() or (root / 'capture-seal.json').exists():
            raise ValueError('Diagnostic audit needs an explicitly marked unsealed fixture')
        scope = 'synthetic diagnostic source and media audit only'
    else:
        if (root / 'fixture-provenance.json').exists():
            raise ValueError('Native alley audit rejects diagnostic fixture')
        verify_native_alley_sources(root, config, case_id)
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
        if any(seal.get('sources', {}).get(name) != digest(root / name) for name in
               (*SOURCES, 'alley-survey-original.json', 'alley-survey-verification.json',
                'construction-probe.json')):
            raise ValueError('Sealed original source hash differs')
        if len(frame_map) != int(config['duration_s'] * config['rate_hz']):
            raise ValueError('Native original duration is incomplete')
        if result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
            raise ValueError('Physical alley passage is unverified')
        visibility = _visibility(root, case_id, len(frame_map), decoded)
        scope = 'source-verified Native alley delivery; legal judgment separate'
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'scope': scope, 'report_sha256': digest(report_path),
            'result_sha256': digest(result_path), 'original_sha256':
            {name: digest(root / name) for name in SOURCES},
            'cameras': decoded, 'frames': len(frame_map),
            'source_decode_receipt_path': str(receipt_path),
            'source_decode_receipt_sha256': digest(receipt_path),
            'source_decode_auditor_sha256': decode['auditor_sha256'],
            'pixel_visibility_review': visibility,
            'checks': {'native_source': not diagnostic_fixture,
                       'all_participants': visibility is not None,
                       'time_join': True, 'full_video_decode': True,
                       'actual_pixels': visibility is not None,
                       'physical_completion': not diagnostic_fixture},
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
