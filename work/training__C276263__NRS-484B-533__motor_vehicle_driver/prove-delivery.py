"""Exercise original-source audit logic with synthetic source-shaped CPU packets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from delivery_audit import REVIEW, audit_attempt
from instrument_producer import audit_stream, build_packet, digest
from measure import SOURCES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, separators=(',', ':')) + '\n' for value in values))


def make_fixture(suffix, destination):
    fixture = ROOT / '.runtime-work' / ('c276263-saved-fixture-' + suffix)
    if not fixture.is_dir():
        raise ValueError('Selected source-shaped fixture missing: ' + suffix)
    shutil.copytree(fixture, destination)
    case = HERE.name + '__' + suffix
    construction = json.loads((HERE / 'selected-grade' / suffix / 'primary' / 'construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    write(destination / 'config.json', config)
    grade = json.loads((destination / 'grade-readback.json').read_text())
    grade['source_kind'] = 'native_map'
    grade['opendrive_sha256'] = sha(destination / 'road.xodr')
    write(destination / 'grade-readback.json', grade)
    vehicle = rows(destination / 'vehicle-frames.jsonl')
    occupancy = rows(destination / 'occupancy-frames.jsonl')
    calibration_survey = {'source_kind': 'original_survey', 'survey_id': 'synthetic-cpu-right-curb',
        'road_id': 1, 'right_curb_y_m': -3.5, 'curb_tangent_heading_world_deg': 0.0,
        'curb_distance_m': 1.75, 'road_xodr_sha256': sha(destination / 'road.xodr')}
    calibration = {'format': 'c276263-curb-calibration-v1', 'calibration_id': 'synthetic-cpu-calibration',
        'source_kind': 'original_survey', 'curb_side': 'right',
        'survey_method': 'synthetic CPU survey-shaped record',
        'sensor_method': 'synthetic CPU wheel-encoder-shaped record',
        'wheel_sensor_id': 'synthetic-cpu-wheel', 'curb_survey_id': 'synthetic-cpu-right-curb',
        'curb_survey': calibration_survey, 'curb_survey_sha256': digest(calibration_survey),
        'curb_tangent_heading_world_deg': 0.0, 'curb_distance_m': 1.75,
        'wheel_zero_offsets_deg': {'front_left': 0.0, 'front_right': 0.0},
        'max_angular_error_deg': 2.0, 'valid_native_frames': [900, 1499]}
    packets = []
    for v, o in zip(vehicle, occupancy):
        frame, actor = v['native_frame'], v['actor_id']
        angle = v['front_wheel_heading_to_curb_deg']
        base = {'source_kind': 'original_sensor', 'native_frame': frame, 'actor_id': actor}
        engine = dict(base, sensor_id='synthetic-cpu-engine', method='engine-shaft-rotation-sensor',
                      engine_running=v['engine_running'])
        wheels = dict(base, sensor_id='synthetic-cpu-wheel', method='front-wheel-optical-encoder',
                      front_wheel_heading_world_deg={'front_left': angle, 'front_right': angle})
        attendance = dict(base, sensor_id='synthetic-cpu-attendance', method='cabin-and-person-tracker',
                          occupant_count=o['occupant_count'],
                          responsible_person_outside=o['responsible_person_outside'],
                          responsible_person_id='synthetic-cpu-person')
        packet = build_packet(frame, actor, {'front_left': angle, 'front_right': angle}, 0.0,
                              calibration, engine, wheels, attendance, diagnostic=False)
        packets.append(packet)
        v.update(source_kind='native_actor', engine_source='instrumented_engine_sensor',
                 wheel_source='instrumented_front_wheel_sensor', brake_source='native_control_readback',
                 engine_method=packet['engine_method'], wheel_calibration_id=packet['wheel_calibration_id'],
                 instrument_id=packet['instrument_id'],
                 front_wheel_angles_native_deg=packet['native_front_wheel_angles_deg'])
        o.update(source_kind='occupancy_sensor', attendance_method=packet['attendance_method'],
                 responsible_person_id=packet['responsible_person_id'], instrument_id=packet['instrument_id'])
    write_rows(destination / 'vehicle-frames.jsonl', vehicle)
    write_rows(destination / 'occupancy-frames.jsonl', occupancy)
    write_rows(destination / 'instrument-frames.jsonl', packets)
    audit = audit_stream(packets)
    write(destination / 'instrument-audit.json', audit)
    write(destination / 'acquisition-provenance.json', {'format': 'c276263-cpu-original-shaped-v1',
        'diagnostic_fixture': False, 'native_vehicle_actor_id': vehicle[0]['actor_id'],
        'synthetic_cpu_test_only': True})
    write(destination / 'engine-preparation.json', {'format': 'c276263-engine-preparation-receipt-v1',
        'case_id': case, 'actor_id': vehicle[0]['actor_id'], 'source_kind': 'original_actuator',
        'requested_engine_running': config['required_original_engine_running'],
        'actuator_accepted': True, 'actuator_id': 'synthetic-cpu-actuator',
        'synthetic_cpu_test_only': True})
    write(destination / 'acquisition-hashes.json', {name: sha(destination / name) for name in SOURCES})
    review = {'format': 'c276263-physical-review-v1', 'case_id': case,
              'calibration_sha256': audit['calibration_sha256'],
              'acquisition_hashes_sha256': sha(destination / 'acquisition-hashes.json'),
              'reviewer_id': 'synthetic-cpu-fixture', 'synthetic_cpu_test_only': True}
    review.update({key: True for key in REVIEW})
    write(destination / 'physical-review.json', review)
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    suffix = args.case.rsplit('__', 1)[-1]
    if suffix not in ('reference', 'contrast', 'engine_on', 'brake_unset', 'wheel_straight'):
        raise ValueError('Unknown exact case')
    with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve(), prefix='c276263-delivery-proof-') as temp:
        root = Path(temp) / 'attempt'
        case = make_fixture(suffix, root)
        if args.negative:
            (root / 'engine-preparation.json').unlink()
        result = audit_attempt(root, case, root / 'physical-review.json')
        print(json.dumps({'case_id': case, 'passed': result['passed'],
                          'synthetic_cpu_fixture': True, 'original_native_executed': False}))


if __name__ == '__main__':
    main()
