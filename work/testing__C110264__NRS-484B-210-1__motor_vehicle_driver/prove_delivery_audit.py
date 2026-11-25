"""Independent CPU audit of explicit diagnostic source shape and rejection.

This never claims a Native run or physical visibility. Production archives are
checked by pass_right_audit.audit_delivery on actual original attempts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from pass_right_measure import load_sealed_trace, observe
from pass_right_route import build_case, load_map_packet


ASSIGNMENT = 'testing__C110264__NRS-484B-210-1__motor_vehicle_driver'


def source(root: Path, spec: dict, label: str) -> Path:
    path = (root / spec['path']).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing required source: original-attempt/' + spec['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != spec['sha256']:
        raise ValueError(label + ' source hash differs')
    return path


def audit(root: Path, case_id: str) -> dict:
    manifest = json.loads((root / 'source-manifest.json').read_text())
    variant = case_id.removeprefix(ASSIGNMENT + '__')
    if (case_id != ASSIGNMENT + '__' + variant or variant not in
            ('left_signal', 'left_turn', 'neither') or manifest.get('case_id') != case_id or
            manifest.get('diagnostic_fixture') is not True or manifest.get('frame_count') != 900):
        raise ValueError('diagnostic exact-case identity mismatch')
    paths = {key: source(root, manifest[key], key) for key in
             ('map', 'route_request', 'trace', 'frame_map')}
    packet = load_map_packet(paths['map'], manifest['map']['sha256'])
    request = json.loads(paths['route_request'].read_text())
    if request != build_case(packet, variant):
        raise ValueError('route request differs from sealed source map')
    trace = load_sealed_trace(paths['trace'], manifest['trace']['sha256'])
    frame_map = json.loads(paths['frame_map'].read_text())
    if len(trace['frames']) != len(frame_map['frames']) or len(trace['frames']) != 900:
        raise ValueError('diagnostic original frame count differs')
    for index, (frame, mapped) in enumerate(zip(trace['frames'], frame_map['frames'])):
        if (frame['native_frame_id'] != mapped['native_frame_id'] or
                frame['camera_frame_ids'] != mapped['camera_frame_ids'] or
                mapped['original_index'] != index):
            raise ValueError('diagnostic Native frame join differs')
    measured = observe(trace)
    if not measured['right_pass_observed'] or not measured['intersection_crossed_during_pass']:
        raise ValueError('diagnostic pass or intersection observation absent')
    if (measured['target_left_signal_during_pass'] != (variant == 'left_signal') or
            measured['target_left_motion_during_pass'] != (variant == 'left_turn')):
        raise ValueError('diagnostic variant observation differs')
    first = trace['frames'][0]
    return {'format': 'worker-right-pass-source-audit', 'assignment_id': ASSIGNMENT,
            'case_id': case_id, 'variant': variant, 'diagnostic_fixture': True,
            'map_sha256': manifest['map']['sha256'],
            'loaded_opendrive_sha256': packet['source_opendrive_sha256'],
            'intersection_s_m': packet['intersection_s_m'], 'fps': 20, 'frame_count': 900,
            'ego_path_s_lateral_m': request['ego_path_s_lateral_m'],
            'initial_ego_s_m': first['ego_s_m'], 'initial_target_s_m': first['target_s_m'],
            'initial_target_lateral_m': first['target_lateral_m'],
            'initial_ego_speed_mps': first['ego_speed_mps'],
            'initial_target_speed_mps': first['target_speed_mps'],
            'actor_half_width_m': packet['actor_half_width_m'],
            'measurement': measured, 'physical_acceptance_claimed': False,
            'legal_outcome': 'unresolved', 'source_scope': 'synthetic diagnostic only'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    root = args.attempt / 'original-attempt'
    if args.mode == 'positive':
        print(json.dumps(audit(root, args.case), sort_keys=True))
    else:
        with tempfile.TemporaryDirectory() as temp:
            damaged = Path(temp) / 'original-attempt'
            shutil.copytree(root, damaged)
            (damaged / 'native/trace.json').unlink()
            audit(damaged, args.case)
            raise AssertionError('missing source unexpectedly accepted')


if __name__ == '__main__':
    main()
