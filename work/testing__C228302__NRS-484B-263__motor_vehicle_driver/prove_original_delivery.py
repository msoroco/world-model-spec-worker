"""Mock-only CPU probe of original exit audit wiring and missing-source rejection."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from delivery_audit import ASSIGNMENT, HERE, audit_attempt
from controlled_access_exit import CASES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def prove(case_id, negative):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    if case_id not in {entry['case_id'] for entry in manifest['cases']}:
        raise ValueError('exact selected exit case required')
    scratch = HERE.parents[1] / '.runtime-work' / 'c228302' / 'tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    if negative:
        audit_attempt(scratch / 'absent-original-attempt', case_id)
        raise ValueError('missing original attempt was accepted')
    short = case_id.removeprefix(ASSIGNMENT + '__')
    case = next(item for item in CASES if item.name == short)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='mock-only-exit-audit-') as dirname:
        root = Path(dirname)
        road = {'map_sha256': 'MOCK ONLY map',
                'controlled_access_readback': True, 'exit_connection_readback': True,
                'exit_waypoints': [[-10, 0, 0], [-3, 0, 0], [5, 0, 0]],
                'highway_approach_waypoints': [[0, -12, 0], [0, -10, 0], [0, 8, 0]],
                'exit_merge_polygon_xy': [[-2, -2], [6, -2], [6, 3], [-2, 3]]}
        for key in ('public_dedication_source_sha256', 'public_access_source_sha256',
                    'restricted_access_authority_source_sha256', 'restricted_access_determination_source_sha256',
                    'highway_boundary_source_sha256', 'exit_connection_source_sha256', 'route_source_sha256'):
            road[key] = 'MOCK ONLY ' + key
        site = {'source_kind': 'original_native_capture', 'reviewer': 'MOCK ONLY',
                'cell_id': 'C228302', 'layout': 'road', 'maneuver': 'exit_road',
                'road': road, 'ego_blueprint': 'mock_ego', 'approach_blueprint': 'mock_approach',
                'ego_blueprint_source_sha256': 'MOCK ONLY ego',
                'approach_blueprint_source_sha256': 'MOCK ONLY approach',
                'driver_control_source_sha256': 'MOCK ONLY controller'}
        site_path = root / 'site-context.json'
        history_path = root / 'original-history.json'
        packet_path = root / 'saved-packet.json'
        write(site_path, site)
        write(history_path, {'mock_only': True})
        measured = {'case_id': short, 'frame_count': 900,
                    'first_entry_frame': 280,
                    'approaching_actor_ids': ['mock_actor_' + str(index)
                                              for index in range(case.approaching_count)],
                    'immediate_hazard_judgment': None,
                    'reasonable_safety_judgment': None}
        cameras = {}
        packet_videos = {}
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            path = root / (name + '.mkv')
            path.write_text('MOCK ONLY ' + name + '\n')
            cameras[name] = {'sha256': sha(path), 'frame_count': 900}
            packet_videos[name] = {'sha256': sha(path), 'decode_receipt_sha256': 'MOCK ONLY receipt',
                                   'decoded_frame_count': 900, 'actual_pixel_audit': True,
                                   'first_original_frame': 100, 'last_original_frame': 999}
        packet = {'case_id': short, 'native_result_sha256': 'MOCK ONLY native',
                  'site_sha256': sha(site_path), 'original_history_sha256': sha(history_path),
                  'frame_count': 900, 'camera_plan_sha256': 'MOCK ONLY camera plan',
                  'frame_map': [{'original_frame': 100 + i, 'elapsed_s': i * .05}
                                for i in range(900)],
                  'videos': packet_videos,
                  'measurement': dict(measured, source_history_sha256=sha(history_path))}
        write(packet_path, packet)
        sources = {name: {'path': name, 'sha256': sha(root / name)}
                   for name in ('site-context.json', 'original-history.json', 'saved-packet.json')}
        sources.update({name + '.mkv': {'path': name + '.mkv', 'sha256': sha(root / (name + '.mkv'))}
                        for name in cameras})
        write(root / 'source-manifest.json', {'case_id': case_id,
                                              'source_kind': 'original_native_capture',
                                              'diagnostic_fixture': False,
                                              'reviewer': 'MOCK ONLY', 'files': sources})
        write(root / 'capture-identity.json', {'case_id': case_id,
                                                'source_kind': 'original_native_capture',
                                                'diagnostic_fixture': False,
                                                'source_manifest_sha256': sha(root / 'source-manifest.json'),
                                                'cameras': cameras})
        with patch('delivery_audit.measure_history', return_value=measured) as measure, \
             patch('delivery_audit.decode_camera', return_value={'frames': 900}) as decode:
            report = audit_attempt(root, case_id)
            measure.assert_called_once()
            if decode.call_count != 4 or report['physical_acceptance'] is not False or report['legal_status'] != 'unresolved':
                raise ValueError('mock-only original audit wiring changed')
    return 'mock-only original exit audit wiring passed: ' + case_id


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative-missing-attempt', action='store_true')
    args = parser.parse_args()
    try:
        print(prove(args.case, args.negative_missing_attempt))
    except ValueError as error:
        print(str(error))
        raise SystemExit(2)
