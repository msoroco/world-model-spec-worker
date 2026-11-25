"""Materialize four exact construction drafts without inventing site sources."""
from __future__ import annotations

import json
from pathlib import Path

from case_protocol import ASSIGNMENT, SUFFIXES, load_case


ROOT = Path(__file__).resolve().parent
SOURCE_CODE = ('runner.py', 'case_protocol.py', 'source_bindings.py',
               'signal_crossing.py', 'native_driver.py', 'native_capture.py',
               'saved_signal_audit.py', 'analysis.py')
CHANNELS = ('ego_body_history', 'other_body_history', 'controller_history', 'ego_entry_frame',
            'other_entry_frame', 'ego_clear_frame', 'other_clear_frame',
            'ego_light_readback', 'official_device_inventory',
            'different_highway_identity')


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def description():
    channels = []
    for name in CHANNELS:
        channels.append({'name': name, 'unit': 'structured record',
                         'sampling_rate_hz': 20,
                         'method': 'saved finalizer from sealed original Native body, device and review sources',
                         'time_window': 'approach through full clearance',
                         'reference_frame': 'original CARLA frame and simulation time',
                         'uncertainty': '20 Hz sampling; physical visibility and legal scope remain reviewed separately'})
    return {'channels': channels,
            'context_inputs': [
                {'name': name, 'unit': 'structured record',
                 'method': 'source-hashed local original review and Native map readback'}
                for name in ('crossing_geometry', 'highway_identity',
                             'device_inventory', 'driver_scope')],
            'limitations': ['Original public roadway and official device review absent in worker export.',
                            'CPU fixtures cannot establish physical camera visibility or legal judgment.']}


def config(spec):
    cameras = []
    for item in json.loads((ROOT / 'camera-plan.json').read_text())['views']:
        cameras.append({'name': item['name'], 'width': item['width'],
                        'height': item['height'], 'pose_strategy': item['subject'],
                        'fov_deg': 90})
    return {'law_id': 'NRS-484B-250-1', 'cell_id': 'C125751',
            'actor': 'motor_vehicle_driver', 'selected_case_id': spec['case_id'],
            'supported_case_ids': [ASSIGNMENT + '__' + suffix for suffix in SUFFIXES],
            'rate_hz': 20, 'duration_s': 55, 'duration_frames': 1100,
            'cameras': cameras, 'required_atoms': [
                'kin.position', 'kin.speed', 'st.intersection',
                'st.lane_enters', 'dev.traffic_signal'],
            'source_packets': [], 'case': {'other_first': spec['other_first'],
                'ego_light_request': spec['ego_light_request'],
                'ego_response_request': spec['ego_response_request']},
            'recording_description': description(),
            'physical_completion': {'format': 'worker-physical-completion-criteria',
                'criterion': 'intersection_clearance',
                'motion_source': 'signal-history.json',
                'body_key': 'frames.ego.body_vertices_xy_m',
                'source_gate': 'reviewed crossing bounds required at local materialization',
                'engineering_tolerances_not_legal': True}}


def construction(spec, relative):
    files = []
    for name in SOURCE_CODE:
        files.append({'path': name,
                      'source': 'work/' + ASSIGNMENT + '/' + name,
                      'content': (ROOT / name).read_text()})
    bundle_test = ROOT / 'tests/test_offline_bundle.py'
    files.append({'path': 'tests/test_offline_bundle.py',
                  'source': 'work/' + ASSIGNMENT + '/tests/test_offline_bundle.py',
                  'content': bundle_test.read_text()})
    for name, source in (('case-spec.json', relative / 'case-spec.json'),
                         ('camera-plan.json', ROOT / 'camera-plan.json'),
                         ('config.json', relative / 'config.json')):
        files.append({'path': name,
                      'source': 'work/' + ASSIGNMENT + '/' + str(source.relative_to(ROOT)),
                      'content': source.read_text()})
    return {'law_id': 'NRS-484B-250-1', 'cell_id': 'C125751',
            'actor': 'motor_vehicle_driver', 'case_id': spec['case_id'],
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': description(),
            'mechanisms': ['source-bound two-route and official-signal preflight',
                           'two vehicle next-tick controls and synchronized four camera capture',
                           'sealed original body, signal and frame histories'],
            'measurement_plan': {'crossing_and_signal': {
                'source': ['signal-history.json', 'source-packet.json', 'review.json',
                           'map.xodr', 'trace.jsonl', 'video_frames.jsonl'],
                'method': 'body-outline entry/clearance, signal readback and frame join'}},
            'static_checks': ['exact source hashes', 'distinct crossing highway routes',
                              'operative official device identity and readback'],
            'termination_rules': ['1100 original frames at 20 Hz or explicit failure status']}


def main():
    for suffix in SUFFIXES:
        relative = ROOT / 'cases' / suffix
        spec = load_case(ROOT, suffix)
        save(relative / 'config.json', config(spec))
        save(relative / 'construction.json', construction(spec, relative))
        if suffix == 'precedence':
            save(ROOT / 'case-spec.json', spec)
            save(ROOT / 'config.json', config(spec))
            save(ROOT / 'construction.json', construction(spec, ROOT))


if __name__ == '__main__':
    main()
