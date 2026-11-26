"""Materialize exact inline constructions from reviewed assignment-local code."""
import json
from pathlib import Path

from package_spec import AID, LAW, CELL, ACTOR, RECORDING, CHANNELS, CAMERAS

HERE = Path(__file__).resolve().parent
SOURCE_FILES = ('runner.py', 'native_source.py', 'contest_aid.py',
                'contest_carla_adapter.py', 'contest_capture.py',
                'analysis.py', 'package_spec.py',
                'tests/test_contest_aid.py', 'tests/test_native_source.py')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('construction exceeds return size limit')


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    base_config = json.loads((HERE / 'config.json').read_text())
    for index, item in enumerate(plan['cases']):
        case_id = item['case_id']
        config = dict(base_config)
        config['cameras'] = CAMERAS
        config['selected_case_id'] = case_id
        config['case'] = dict(base_config['case'])
        config['case']['case_id'] = case_id
        config['case']['physical_risk'] = item['physical_risk']
        config['case']['recording_description'] = RECORDING
        files = [{'path': name, 'content': (HERE / name).read_text()}
                 for name in SOURCE_FILES]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2, ensure_ascii=False) + '\n'})
        construction = {
            'law_id': LAW, 'cell_id': CELL, 'actor': ACTOR,
            'case_id': case_id, 'entrypoint': 'runner.py',
            'recording_description': RECORDING, 'files': files,
            'measurement_plan': {'rate_hz': 20, 'duration_s': 45,
                                 'required_channels': [name for name, _, _ in CHANNELS]},
            'static_checks': ['source hashes and exact case identity',
                              'two distinct Native motor vehicles and route readback',
                              'physical cue light readback and four camera frame join'],
            'termination_rules': ['900 consecutive original Native frames at 20 Hz',
                                  'brake, destroy owned actors and restore world on every exit'],
            'mechanisms': ['reviewed Native source packet and route',
                           'two-vehicle physical motion controller and cue',
                           'saved-only source-joined finalization']}
        suffix = case_id.removeprefix(AID + '__')
        write(HERE / 'cases' / suffix / 'construction.json', construction)
        if index == 0:
            write(HERE / 'construction.json', construction)
            write(HERE / 'config.json', config)
    return len(plan['cases'])


if __name__ == '__main__':
    print('exact inline constructions:', build())
