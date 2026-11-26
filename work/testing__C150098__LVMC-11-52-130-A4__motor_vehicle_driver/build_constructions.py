"""Materialize eleven exact source-gated hydrant bundles for CPU offline checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hydrant import ASSIGNMENT, CASES

HERE = Path(__file__).resolve().parent
VIEWS = (('overview', 1920, 1080), ('approach', 1280, 720),
         ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
SCRIPTS = ('runner.py', 'native_runner.py', 'native_packet.py', 'hydrant.py',
           'saved_audit.py', 'analysis.py')


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('construction file exceeds 2 MiB')


def recording_description():
    specs = (
        ('longitudinal_hydrant_gap', 'metres', 'original body edge and physical hydrant extent'),
        ('parallel_parking_authority', 'reviewed source', 'location-specific municipal permission'),
        ('vehicle_activity', 'original observation', 'stop, stand or park in complete history'),
        ('exception_source', 'reviewed source', 'lawful traffic conflict, police or device direction'),
        ('camera_frame_identity', 'frame ID', 'four synchronized original camera views'),
    )
    return {'channels': [{'name': name, 'unit': unit, 'method': method,
                          'sampling_rate_hz': 20, 'time_window': 'all 900 original frames',
                          'reference_frame': 'original Native frame, reviewed hydrant and map',
                          'uncertainty': 'requested gap and synthetic fixtures do not establish legal or physical outcome'}
                         for name, unit, method in specs],
            'context_inputs': [], 'limitations': [
                'The legal distance convention requires independent source review.',
                'Municipal permission and exception necessity require original authority sources.']}


def make_config(case):
    ids = [ASSIGNMENT + '__' + item.suffix for item in CASES]
    return {'assignment_id': ASSIGNMENT, 'law_id': 'LVMC-11-52-130-A4',
            'cell_id': 'C150098', 'actor': 'motor_vehicle_driver',
            'selected_case_id': ASSIGNMENT + '__' + case.suffix,
            'supported_case_ids': ids, 'rate_hz': 20, 'duration_s': 45,
            'frame_count': 900, 'required_atoms': [], 'source_packets': [],
            'requested_side': case.side, 'requested_gap_m': case.gap_m,
            'requested_activity': case.activity, 'requested_exception': case.exception,
            'cameras': [{'name': name, 'width': width, 'height': height,
                         'pose_strategy': 'reviewed original four-view site survey',
                         'fov_deg': 90} for name, width, height in VIEWS],
            'case': {'case_id': ASSIGNMENT + '__' + case.suffix,
                     'recording_description': recording_description()}}


def build():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    ids = [ASSIGNMENT + '__' + case.suffix for case in CASES]
    if [case['case_id'] for case in plan['cases']] != ids:
        raise ValueError('frozen eleven-case plan changed')
    branch = plan['selected_branches'][0]
    plan['selected_branch'] = branch['branch']
    plan['requirement_dispositions'] = [{
        'requirement': branch['requirement'], 'source': branch['source'],
        'status': 'selected_required', 'case_ids': ids,
        'evidence_or_gap': 'No accepted original hydrant recording in exported inventory.',
        'reason': 'Physical hydrant, parallel parking permission and source-bound activity need original capture.'}]
    plan['observations'] = [{'name': name, 'mandatory': True} for name in
        ('longitudinal_hydrant_gap', 'parallel_parking_authority',
         'vehicle_activity', 'exception_source', 'camera_frame_identity')]
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'view': name, 'subject': subject,
                      'interval': 'all original 900 frames'} for (name, _, _), subject in zip(VIEWS,
            ('hydrant, curb and ego', 'one-way approach and ego body',
             'physical hydrant and body edge', 'driver reference and directions'))]}
    for row in plan['cases']:
        row['kind'] = 'delivery'
        row['new_capture_selected'] = True
        row['construction_status'] = 'source_gated_exact_bundle'
    write(plan_path, plan)
    code = {name: (HERE / name).read_text(encoding='utf-8') for name in SCRIPTS}
    description = recording_description()
    for index, case in enumerate(CASES):
        case_id = ids[index]
        config = make_config(case)
        config_text = json.dumps(config, indent=2) + '\n'
        test_text = ('"""Exact source-gated hydrant materialization."""\n'
                     'import unittest\n'
                     'import sys\n'
                     'from pathlib import Path\n'
                     'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n'
                     'from runner import check\n\n'
                     'class ExactBundleTest(unittest.TestCase):\n'
                     '    def test_selected_identity(self):\n'
                     '        self.assertTrue(check().endswith("__' + case.suffix + '"))\n')
        files = [{'path': name, 'content': content} for name, content in code.items()]
        files += [{'path': 'config.json', 'content': config_text},
                  {'path': 'tests/test_bundle.py', 'content': test_text}]
        construction = {'law_id': 'LVMC-11-52-130-A4', 'cell_id': 'C150098',
            'actor': 'motor_vehicle_driver', 'case_id': case_id,
            'entrypoint': 'runner.py', 'diagnostic_only': True,
            'recording_description': description, 'files': files,
            'measurement_plan': '900 original body-to-hydrant gap, parking authority and activity observations',
            'static_checks': ['reviewed source hashes', 'exact case and one-way approach',
                              'physical hydrant readback', 'four camera frame joins'],
            'termination_rules': ['900 synchronized Native ticks', 'restore world'],
            'mechanisms': ['source-gated physical hydrant and ego spawn',
                           'four-camera Native capture with sealed original history']}
        write(HERE / ('construction-' + case.suffix + '.json'), construction)
        if index == 0:
            (HERE / 'config.json').write_text(config_text, encoding='utf-8')
            (HERE / 'tests/test_bundle.py').write_text(test_text, encoding='utf-8')
            write(HERE / 'construction.json', construction)
    return ids


if __name__ == '__main__':
    print('\n'.join(build()))
