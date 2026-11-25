"""Bind the existing reference construction to an exact two-case source plan.

This is a partial selected scaffold. It does not create proof receipts or claim
that a lamp request established its observed colour, distance or timing.
"""
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    plan_path = PACKAGE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    names = {item['name'] for item in plan['observations']}
    names.update(channel for mapping in plan['source_observation_mapping'].values()
                 for channel in mapping['channels'])
    names.update(('native_lighting_frames', 'four_camera_video'))
    draft = json.loads((PACKAGE / 'draft-primary/reference/primary/construction.json').read_text())
    config = json.loads(next(item['content'] for item in draft['files']
                             if item['path'] == 'config.json'))
    config['supported_case_ids'] = [case['case_id'] for case in plan['cases']]
    config['case'] = {'case_id': config['case_id'],
                      'requested_setting': 'reference'}
    config['recording_description'] = {
        'channels': [{'name': name, 'unit': 'structured' if name not in
                      ('speed_mps', 'front_visible_ft', 'rear_visible_ft', 'utc_s',
                       'sunset_utc_s', 'next_sunrise_utc_s') else 'number',
                      'sampling_rate_hz': 20,
                      'method': 'Original Native capture or independently calibrated saved review; source provenance required',
                      'time_window': '600 frames',
                      'reference_frame': 'Native capture frame and synchronized camera frame',
                      'uncertainty': 'Synthetic fixture only; original calibration, lamp reach and discernibility require independent review'}
                     for name in sorted(names)],
        'context_inputs': draft['recording_description']['context_inputs'],
        'limitations': draft['recording_description']['limitations'],
    }
    config['case']['recording_description'] = config['recording_description']
    write(PACKAGE / 'config.json', config)
    runner = next(item['content'] for item in draft['files'] if item['path'] == 'runner.py')
    (PACKAGE / 'runner.py').write_text(runner)
    tests = next(item['content'] for item in draft['files']
                 if item['path'] == 'tests/test_offline.py')
    (PACKAGE / 'tests').mkdir(exist_ok=True)
    (PACKAGE / 'tests/test_offline.py').write_text(tests)
    construction = dict(draft)
    construction['recording_description'] = config['recording_description']
    construction['status'] = 'selected_scaffold_unproven'
    construction['files'] = [dict(item, content=(PACKAGE / item['path']).read_text())
                             if item['path'] in ('runner.py', 'config.json',
                                                 'tests/test_offline.py') else item
                             for item in draft['files']]
    for name in ('selected_finalize.py', 'selected_source_analysis.py',
                 'bind_lighting_sources.py', 'join_lighting_review.py',
                 'measure_lighting.py'):
        source = PACKAGE / 'native' / name
        construction['files'].append({
            'path': name, 'source': str(source.relative_to(PACKAGE.parents[1])),
            'content': source.read_text(),
        })
    write(PACKAGE / 'construction.json', construction)
    proposal = {
        'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
        'sweeps_expanded': True, 'sweep_specs': [], 'cases': [
            {'case_id': case['case_id'], 'target_law_id': plan['law_id'],
             'target_type': 'attempt',
             'rationale': 'Controlled requested lamp-state contrast; measure original lamp and visibility sources before review',
             'variable_assignments': {'requested_light_state':
                                      'LowBeam|Position' if case['requested_setting'] == 'reference'
                                      else 'Position'},
             'unresolved_judgment_calls': ['actual headlamp range and rear discernibility',
                                           'original civil time and covered vehicle class'],
             'recording_description': config['recording_description']}
            for case in plan['cases']],
    }
    write(PACKAGE / 'proposals/cases.json', proposal)
    methods = ('equipment_observations', 'burning_observations', 'scope_observations')
    inputs = (('lighting-review.jsonl', 'lighting-measure-context.json'),
              ('native-lighting-frames.jsonl', 'lighting-review.jsonl',
               'lighting-measure-context.json'),
              ('lighting-review-context.json', 'video_frames.jsonl'))
    for case in plan['cases']:
        contract = {
            'format': 'worker-measurement-contract', 'case_id': case['case_id'],
            'requirements': [
                {'disposition_index': index,
                 'requirement': disposition['requirement'],
                 'source': disposition['source'],
                 'output_key': method, 'method': method,
                 'value_type': 'object', 'kind': 'measured',
                 'inputs': list(sources)}
                for index, (disposition, method, sources) in
                enumerate(zip(plan['requirement_dispositions'], methods, inputs))],
            'negative': {'remove': ['lighting-measure-context.json'],
                         'error_contains': 'Missing required source: lighting-measure-context.json'},
        }
        write(PACKAGE / ('measurement-contract-' + case['requested_setting'] + '.json'), contract)
    plan['camera_plan'] = {
        'profile': 'overview1080-capability',
        'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'motorcycle, rear and road context',
             'interval': '600 frames'},
            {'view': 'approach', 'subject': 'forward lamp reach and 500 ft context',
             'interval': '600 frames'},
            {'view': 'reference_corner', 'subject': 'front and rear lamp placement',
             'interval': '600 frames'},
            {'view': 'driver_reference', 'subject': 'rider forward context',
             'interval': '600 frames'},
        ],
    }
    write(plan_path, plan)
    print(json.dumps({'scaffold': True, 'cases': len(plan['cases']),
                      'source_channels': len(names), 'delivery_ready': False}))


if __name__ == '__main__':
    build()
