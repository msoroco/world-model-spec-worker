"""Independent saved-source audit for one exact C158190 yield case."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from worker_exchange.media import audit as audit_video
from worker_exchange.measurement_contract import validate, verify_report

ROOT = Path(__file__).resolve().parent
CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
PREFIX = 'testing__C158190__NRS-484B-257-1__motor_vehicle_driver__'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(attempt, case_id, *, diagnostic_fixture=False):
    attempt = Path(attempt)
    if not case_id.startswith(PREFIX):
        raise ValueError('Wrong exact C158190 case')
    config = json.loads((attempt / 'config.json').read_text())
    if (config.get('selected_case_id') != case_id or config.get('law_id') != 'NRS-484B-257-1'
            or config.get('cell_id') != 'C158190' or config.get('rate_hz') != 20
            or config.get('duration_s') != 30):
        raise ValueError('Exact case or capture profile changed')
    mapping_path = attempt / 'video_frames.jsonl'
    mapping = rows(mapping_path)
    if len(mapping) != 600:
        raise ValueError('Full original 600-frame map required')
    for index, row in enumerate(mapping):
        if (row.get('video_frame') != index or type(row.get('carla_frame')) is not int
                or type(row.get('time_s')) not in (int, float)
                or not math.isfinite(row['time_s'])):
            raise ValueError('Original frame/time join invalid')
        if index and (row['carla_frame'] != mapping[index - 1]['carla_frame'] + 1
                      or abs(row['time_s'] - mapping[index - 1]['time_s'] - .05) > 1e-3):
            raise ValueError('Original frame/time sequence is not 20 Hz')
    interaction = rows(attempt / 'interaction_history.jsonl')
    if len(interaction) != 600:
        raise ValueError('Full original actor-body history required')
    if [row.get('frame') for row in interaction] != [row['carla_frame'] for row in mapping]:
        raise ValueError('Original actor-body frame join changed')
    if any(not row.get('ego', {}).get('body_vertices_m') for row in interaction):
        raise ValueError('Missing original ego body geometry')
    in_junction = [any(-8 <= point[0] <= 8 and -8 <= point[1] <= 8
                       for point in row['ego']['body_vertices_m']) for row in interaction]
    if not any(in_junction) or not any(
            all(point[0] > 8 for point in row['ego']['body_vertices_m'])
            for row in interaction[in_junction.index(True) + 1:]):
        raise ValueError('Original ego body did not enter and fully exit junction')
    if case_id.endswith('__yield_nearest_view_clear'):
        if any(row.get('through') is not None for row in interaction):
            raise ValueError('Clear case contains a through vehicle')
    elif any(not row.get('through', {}).get('body_vertices_m') for row in interaction):
        raise ValueError('Through-traffic case lacks original actor body')
    result = json.loads((attempt / 'result.json').read_text())
    maneuver = result.get('physical_checks', {}).get('maneuver', {})
    if (result.get('case_id') != case_id or result.get('maneuver_completed') is not True
            or maneuver.get('status') != 'met'
            or maneuver.get('sources', {}).get('interaction_history.jsonl') !=
            sha(attempt / 'interaction_history.jsonl')):
        raise ValueError('Sealed maneuver result lacks original body proof')
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    contract = json.loads((ROOT / 'measurement-contract.json').read_text())
    validate(contract, plan['requirement_dispositions'],
             (ROOT / 'finalizer.py').read_text(), case_id)
    analysis_path = attempt / 'analysis-report.json'
    analysis = json.loads(analysis_path.read_text())
    verified = verify_report(contract, analysis, attempt)
    if len(verified) != 7:
        raise ValueError('Seven source-bound selected measurements required')
    review = json.loads((attempt / 'rendered_marking_review.json').read_text())
    if (review.get('method') != 'original_source_camera_frame_review'
            or review.get('reviewed_frame_count') != 600
            or review.get('reviewed_carla_frames') != [row['carla_frame'] for row in mapping]
            or review.get('yield_sign_face_visible') is not True
            or any(review.get(name) is not True for name in
                   ('no_stop_line', 'no_near_crosswalk', 'no_police_direction',
                    'no_traffic_signal_control'))):
        raise ValueError('Original-camera sign/control review incomplete')
    if not diagnostic_fixture and (not review.get('reviewer') or
                                   str(review['reviewer']).startswith('synthetic-')):
        raise ValueError('Independent original-camera pixel reviewer required')
    if not diagnostic_fixture and result.get('provenance_kind') != 'native':
        raise ValueError('Native source provenance required')
    decoded = {}
    for name, dimensions in CAMERAS.items():
        source = attempt / (name + '.mkv')
        if not source.is_file() or review.get('source_sha256', {}).get(source.name) != sha(source):
            raise ValueError('Missing or changed original camera: ' + source.name)
        media = audit_video(source, 600, mapping_sha256=sha(mapping_path))
        if media.get('dimensions') != list(dimensions):
            raise ValueError('Original camera dimensions changed: ' + source.name)
        decoded[source.name] = media['video_sha256']
    return {'format': 'worker-c158190-independent-source-audit',
            'case_id': case_id, 'original_frames': 600,
            'frame_map_sha256': sha(mapping_path),
            'actor_history_sha256': sha(attempt / 'interaction_history.jsonl'),
            'sealed_result_sha256': sha(attempt / 'result.json'),
            'analysis_sha256': sha(analysis_path),
            'verified_measurements': sorted(verified), 'source_cameras': decoded,
            'software_audit_passed': True,
            'physical_acceptance_claimed': False,
            'legal_conclusion': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case,
                           diagnostic_fixture=args.diagnostic_fixture), indent=2))


if __name__ == '__main__':
    main()
