"""Exercise exact crossing motion outcomes from synthetic original-frame traces."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from entry_timing import ASSIGNMENT, CASES, measure

HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source(suffix):
    root = HERE/'fixture-precedence' if suffix == 'precedence' else HERE/'fixture-variants'/suffix
    trace_path = root/'original-trace.json'
    survey_path = HERE/'fixture-precedence/crossing-survey.json'
    trace = json.loads(trace_path.read_text())
    survey = json.loads(survey_path.read_text())
    if trace['case_id'] != ASSIGNMENT+'__'+suffix:
        raise ValueError('wrong exact synthetic source case')
    return trace, survey, {'original_trace_sha256': digest(trace_path.read_bytes()),
                           'survey_sha256': digest(survey_path.read_bytes())}


def probe(trace, survey, sources, kind):
    test_trace = copy.deepcopy(trace)
    if kind == 'incomplete_motion':
        for row in test_trace['frames'][75:]:
            row['ego']['body_vertices_xy_m'] = [[-.2, -.2], [.2, -.2], [.2, .2], [-.2, .2]]
    elif kind == 'missing_evidence':
        del test_trace['frames'][75]['ego']
    elif kind != 'complete_motion':
        raise ValueError('unknown physical diagnostic outcome')
    diagnostic_hash = digest(json.dumps(test_trace, sort_keys=True).encode())
    try:
        observation = measure(test_trace, survey)
    except ValueError as error:
        if kind != 'missing_evidence':
            raise
        status, explanation = 'unverified', str(error)
        observation = None
    else:
        completed = observation['entry_brackets']['ego'] is not None and observation['exit_brackets']['ego'] is not None
        status = 'met' if completed else 'not_met'
        expected = 'met' if kind == 'complete_motion' else 'not_met'
        if status != expected:
            raise ValueError('synthetic motion outcome differs from expected diagnostic')
        explanation = 'ego full body entered and exited' if completed else 'ego full body did not exit'
    if kind == 'missing_evidence' and 'original actor' not in explanation:
        raise ValueError('missing source did not trigger actor-evidence rejection')
    return {'case_id': trace['case_id'], 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'maneuver_completed': status == 'met',
            'physical_checks': {'maneuver': {'status': status,
                'method': '900 original-frame full-body entry and exit transitions with missing-source rejection',
                'sources': {**sources, 'diagnostic_trace_sha256': diagnostic_hash},
                'detail': explanation}},
            'realized_observables': {'ego_exit_bracket': observation['exit_brackets']['ego']}
                                    if observation is not None and status == 'met' else {},
            'scope': 'synthetic CPU motion outcome; no CARLA physical acceptance'}


def lifecycle():
    def check(events):
        if events != EVENTS:
            raise ValueError('saved processing before original Native ownership closure')
    check(EVENTS)
    try:
        check(EVENTS[:4] + [EVENTS[5], EVENTS[4]])
    except ValueError:
        return EVENTS
    raise ValueError('bad lifecycle ordering was accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    if not args.case.startswith(ASSIGNMENT+'__'):
        raise ValueError('foreign exact case')
    suffix = args.case.removeprefix(ASSIGNMENT+'__')
    if suffix not in CASES:
        raise ValueError('unknown exact case')
    trace, survey, sources = source(suffix)
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = probe(trace, survey, sources, kind)
        (HERE/f'physical-{suffix}-{kind}.json').write_text(json.dumps(result, indent=2)+'\n')
        print(kind, result['physical_checks']['maneuver']['status'])
    print('lifecycle', ','.join(lifecycle()))


if __name__ == '__main__':
    main()
