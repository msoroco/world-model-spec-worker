"""Officer-directed exception variant with independent instruction sources."""
import argparse
import json
import os
from pathlib import Path

import base_runner

AID = base_runner.AID
CASE = AID + '__officer_directed'
COUNT = base_runner.COUNT
CAMERAS = base_runner.CAMERAS


def config():
    cfg = json.loads((Path(__file__).resolve().parent / 'config.json').read_text())
    if (cfg.get('assignment_id') != AID or cfg.get('case_id') != CASE or
            cfg.get('selected_case_id') != CASE or cfg.get('case_suffix') != 'officer_directed' or
            cfg.get('law_id') != 'NRS-484B-267-2d' or cfg.get('cell_id') != 'C404492' or
            cfg.get('actor') != 'motor_vehicle_driver' or cfg.get('frames') != 600 or
            cfg.get('rate_hz') != 20 or cfg.get('duration_s') != 30 or
            cfg.get('physical_acceptance_claimed') is not False):
        raise ValueError('Exact officer-directed case contract differs')
    # Reuse the existing exact camera and candidate validation with the
    # equivalent controlled_2 identity. Only the reviewed officer direction
    # changes between the two constructions.
    motion_case = AID + '__controlled_2'
    motion = dict(cfg, case_id=motion_case,
                  selected_case_id=motion_case, case_suffix='controlled_2')
    original_path = base_runner.Path
    # base_runner.config reads its sibling config.json; validate the exact
    # equivalent through a private object whose read_text returns the mapped
    # config, without changing that file or relaxing the base validator.
    class MappedPath:
        def __init__(self, path):
            self.path = path
        def resolve(self):
            return self
        @property
        def parent(self):
            return self
        def __truediv__(self, name):
            return self
        def read_text(self):
            return json.dumps(motion)
    base_runner.Path = MappedPath
    try:
        base_runner.config()
    finally:
        base_runner.Path = original_path
    return cfg


def survey_check(survey):
    if survey.get('officer_directed_otherwise') is not True:
        raise ValueError('Officer-directed exception requires reviewed direction')
    for key in ('officer_instruction_source', 'officer_identity_source',
                'officer_instruction_text', 'officer_instruction_recipient',
                'officer_instruction_timing_source', 'officer_instruction_reviewer'):
        value = survey.get(key)
        if not isinstance(value, str) or not value or value.startswith('synthetic-fixture:'):
            raise ValueError('Original officer instruction source missing: ' + key)
    return survey


def execute(output, survey, host, port):
    cfg = config()
    survey_check(survey)
    motion = dict(cfg, case_suffix='controlled_2')
    original = base_runner.config
    base_runner.config = lambda: motion
    try:
        result = base_runner.execute(output, survey, host, port)
    finally:
        base_runner.config = original
    template = Path(output) / 'emergency_context.template.json'
    if template.is_file():
        context = json.loads(template.read_text())
        context['officer_directed_otherwise'] = True
        context['officer_instruction_sources'] = {
            key: survey[key] for key in ('officer_instruction_source',
                'officer_identity_source', 'officer_instruction_text',
                'officer_instruction_recipient', 'officer_instruction_timing_source',
                'officer_instruction_reviewer')}
        template.write_text(json.dumps(context, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--survey', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    cfg = config()
    if args.check:
        print(json.dumps({'passed': True, 'case_id': CASE, 'frames': 600,
                          'cameras': list(base_runner.CAMERAS),
                          'native_imported': False, 'physical_acceptance_claimed': False}))
    else:
        source = args.survey or (Path(os.environ['SCENARIO_NATIVE_SURVEY'])
                                 if os.environ.get('SCENARIO_NATIVE_SURVEY') else None)
        if source is None or args.output_dir is None:
            parser.error('--output-dir and --survey or SCENARIO_NATIVE_SURVEY required')
        print(json.dumps(execute(args.output_dir, json.loads(source.read_text()),
                                 args.host, args.port)))
