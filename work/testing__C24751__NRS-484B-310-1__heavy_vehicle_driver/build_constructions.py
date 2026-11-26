"""Materialize four exact C24751 source-gated bundles for offline checks."""
from __future__ import annotations

import json
from pathlib import Path

from flashing_red_native import ASSIGNMENT, CASES
from native_packet import VIEWS

HERE = Path(__file__).resolve().parent
SCRIPTS = ('runner.py', 'native_runner.py', 'native_packet.py',
           'flashing_red_native.py', 'flashing_red_probe.py', 'analysis.py')


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('construction exceeds 2 MiB')


def description():
    channels = (('signal_flash', 'boolean', 'source-bound red lens illumination per frame'),
                ('front_position', 'metres', 'heavy-vehicle front body coordinate'),
                ('complete_cessation', 'boolean', 'original zero-motion observation'),
                ('stop_reference', 'surveyed coordinate', 'selected physical reference alternative'),
                ('occluder_source', 'source hash', 'physical occluder and geometry readback'),
                ('camera_frame_identity', 'frame ID', 'four synchronized original views'))
    return {'channels': [{'name': name, 'unit': unit, 'method': method,
                          'sampling_rate_hz': 20, 'time_window': 'all 900 original frames',
                          'reference_frame': 'original Native frame and reviewed map',
                          'uncertainty': 'requested stop target does not prove physical or legal outcome'}
                         for name, unit, method in channels],
            'context_inputs': [], 'limitations': [
                'Right to proceed after the stop requires separate applicable-rule review.',
                'No numeric legal speed or stopping tolerance is inferred.']}


def make_config(case):
    ids = [ASSIGNMENT + '__' + item.suffix for item in CASES]
    return {'assignment_id': ASSIGNMENT, 'law_id': 'NRS-484B-310-1',
            'cell_id': 'C24751', 'actor': 'heavy_vehicle_driver',
            'selected_case_id': ASSIGNMENT + '__' + case.suffix,
            'supported_case_ids': ids, 'rate_hz': 20, 'duration_s': 45,
            'frame_count': 900, 'required_atoms': [], 'source_packets': [],
            'requested_reference': case.reference,
            'requested_stop_offset_m': case.stop_offset_m,
            'cameras': [{'name': name, 'width': width, 'height': height,
                         'pose_strategy': 'reviewed original four-view site survey',
                         'fov_deg': 90} for name, width, height in VIEWS],
            'case': {'case_id': ASSIGNMENT + '__' + case.suffix,
                     'recording_description': description()}}


def build():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    ids = [ASSIGNMENT + '__' + case.suffix for case in CASES]
    if [row['case_id'] for row in plan['cases']] != ids:
        raise ValueError('exact four-case plan changed')
    branch = plan['selected_branches'][0]
    plan['selected_branch'] = branch['branch']
    plan['requirement_dispositions'] = [{
        'requirement': branch['requirement'], 'source': branch['source'],
        'status': 'selected_required', 'case_ids': ids,
        'evidence_or_gap': 'No accepted original flashing-red recording in frozen inventory.',
        'reason': 'Official signal, obstruction, heavy-vehicle motion and stop geometry need original capture.'}]
    plan['observations'] = [{'name': channel['name'], 'mandatory': True}
                            for channel in description()['channels']]
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'view': name, 'subject': subject,
                      'interval': 'all original 900 frames'} for (name, _, _), subject in zip(VIEWS,
            ('signal, intersection and heavy vehicle', 'blind approach and vehicle',
             'physical flashing lens and stop reference', 'driver approach and occluder'))]}
    for row in plan['cases']:
        row['new_capture_selected'] = True
        row['construction_status'] = 'source_gated_exact_bundle'
    write(plan_path, plan)
    code = {name: (HERE / name).read_text(encoding='utf-8') for name in SCRIPTS}
    for index, case in enumerate(CASES):
        case_id = ids[index]
        config = make_config(case)
        config_text = json.dumps(config, indent=2) + '\n'
        test_text = ('"""Exact source-gated flashing-red materialization."""\n'
                     'import unittest\nimport sys\nfrom pathlib import Path\n'
                     'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n'
                     'from runner import check\n\nclass ExactBundleTest(unittest.TestCase):\n'
                     '    def test_selected_identity(self):\n'
                     '        self.assertTrue(check().endswith("__' + case.suffix + '"))\n')
        files = [{'path': name, 'content': content} for name, content in code.items()]
        files += [{'path': 'config.json', 'content': config_text},
                  {'path': 'tests/test_bundle.py', 'content': test_text}]
        construction = {'law_id': 'NRS-484B-310-1', 'cell_id': 'C24751',
            'actor': 'heavy_vehicle_driver', 'case_id': case_id,
            'entrypoint': 'runner.py', 'diagnostic_only': True,
            'recording_description': description(), 'files': files,
            'measurement_plan': '900 original flashing lens, front body, stop and occluder observations',
            'static_checks': ['reviewed source hashes', 'governed official signal',
                              'physical occluder readback', 'heavy vehicle dimensions',
                              'four camera frame joins'],
            'termination_rules': ['900 synchronized Native ticks', 'restore world'],
            'mechanisms': ['source-gated physical signal and occluder',
                           'heavy-vehicle route and stop target',
                           'four-camera Native capture with sealed original history']}
        write(HERE / ('construction-' + case.suffix + '.json'), construction)
        if index == 0:
            (HERE / 'config.json').write_text(config_text, encoding='utf-8')
            (HERE / 'tests/test_bundle.py').parent.mkdir(parents=True, exist_ok=True)
            (HERE / 'tests/test_bundle.py').write_text(test_text, encoding='utf-8')
            write(HERE / 'construction.json', construction)
    return ids


if __name__ == '__main__':
    print('\n'.join(build()))
