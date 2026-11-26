"""Independent paired audit of original trail attempts after delivery review."""
import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_DELIVERY_CHECKS = ('native_source', 'all_participants', 'time_join',
                            'full_video_decode', 'actual_pixels', 'physical_completion')
REQUEST_KEY = {'occupancy': None, 'designation': 'official_designation',
               'dedication': 'city_dedication', 'posting': 'appropriate_posting',
               'emergency': 'exception_kind', 'maintenance': 'exception_kind'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def original(attempt_path, receipt_path, case_id):
    attempt = Path(attempt_path).resolve()
    receipt = read(receipt_path)
    result_path = attempt / 'result.json'
    config_path = attempt / 'config.json'
    road_path = attempt / 'road.xodr'
    context_path = attempt / 'trail-authority-context.json'
    poses_path = attempt / 'vehicle-poses.jsonl'
    frames_path = attempt / 'video_frames.jsonl'
    cameras_path = attempt / 'camera-frames.jsonl'
    for path in (result_path, config_path, road_path, context_path,
                 poses_path, frames_path, cameras_path):
        if not path.is_file():
            raise ValueError('Missing original comparison source: ' + path.name)
    result, config, context = read(result_path), read(config_path), read(context_path)
    if (receipt.get('format') != 'worker-delivery-audit' or receipt.get('passed') is not True
            or receipt.get('case_id') != case_id or
            receipt.get('source_result_sha256') != sha(result_path) or
            any(receipt.get('checks', {}).get(check) is not True
                for check in REQUIRED_DELIVERY_CHECKS)):
        raise ValueError('Independent delivery acceptance absent')
    if (result.get('case_id') != case_id or config.get('case_id') != case_id or
            result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False
            or result.get('maneuver_completed') is not True):
        raise ValueError('Original case and physical completion absent')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-27-010-A', 'C143691', 'motor_vehicle_driver'):
        raise ValueError('Fixed assignment scope differs')
    if (config.get('rate_hz'), config.get('duration_s'),
            tuple(camera.get('name') for camera in config.get('cameras', []))) != (
            20, 30, ('overview', 'approach', 'reference_corner', 'driver_reference')):
        raise ValueError('Fixed camera and duration plan differs')
    if context.get('request') != config.get('source_context_request'):
        raise ValueError('Original trail request/source mismatch')
    poses, frames, cameras = [path.read_text().splitlines() for path in (
        poses_path, frames_path, cameras_path)]
    if (len(poses), len(frames), len(cameras)) != (600, 600, 2400):
        raise ValueError('Original comparison frame counts differ')
    measured = result.get('measured_values', {})
    if type(measured.get('occupancy_frames')) is not int or not 0 <= measured['occupancy_frames'] <= 600:
        raise ValueError('Original measured trail occupancy absent')
    return {'case_id': case_id, 'request': context['request'],
            'route_case': config['route_case'], 'road_sha256': sha(road_path),
            'camera_plan': config['cameras'], 'occupancy_frames': measured['occupancy_frames'],
            'blueprint_id': measured.get('vehicle_blueprint_id'),
            'result_sha256': sha(result_path), 'delivery_receipt_sha256': sha(receipt_path)}


def audit(spec, left, right):
    comparison_id = spec['comparison_id']
    name = comparison_id.rsplit('__', 1)[-1]
    if name not in REQUEST_KEY or spec['case_ids'] != [left['case_id'], right['case_id']]:
        raise ValueError('Exact comparison identity differs')
    if left['road_sha256'] != right['road_sha256'] or left['camera_plan'] != right['camera_plan']:
        raise ValueError('Fixed road or camera plan differs')
    changed = {key for key in left['request'] if left['request'][key] != right['request'].get(key)}
    expected = set() if name == 'occupancy' else {REQUEST_KEY[name]}
    if changed != expected or set(right['request']) != set(left['request']):
        raise ValueError('Comparison changed unexpected source condition')
    if name == 'occupancy':
        if (left['route_case'], right['route_case']) != ('outside', 'within'):
            raise ValueError('Occupancy route requests differ')
        if not left['occupancy_frames'] == 0 or not right['occupancy_frames'] > 0:
            raise ValueError('Measured occupancy distinction absent')
    else:
        if left['route_case'] != right['route_case'] or left['occupancy_frames'] == 0 or right['occupancy_frames'] == 0:
            raise ValueError('Fixed within-trail route/occupancy differs')
    if name in ('designation', 'dedication', 'posting') and left['blueprint_id'] != right['blueprint_id']:
        raise ValueError('Fixed subject blueprint differs')
    return {'format': 'c143691-original-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': spec['case_ids'],
            'passed': True, 'changed_request_keys': sorted(changed),
            'left_result_sha256': left['result_sha256'],
            'right_result_sha256': right['result_sha256'],
            'delivery_receipt_sha256': [left['delivery_receipt_sha256'],
                                        right['delivery_receipt_sha256']],
            'original_review_required': True, 'legal_outcome_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left-attempt', required=True)
    parser.add_argument('--left-delivery-receipt', required=True)
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--right-delivery-receipt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parents[1]
    spec = next(row for row in read(here / 'case-plan.json')['comparisons']
                if row['comparison_id'] == args.comparison)
    receipt = audit(spec,
                    original(args.left_attempt, args.left_delivery_receipt, spec['case_ids'][0]),
                    original(args.right_attempt, args.right_delivery_receipt, spec['case_ids'][1]))
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
