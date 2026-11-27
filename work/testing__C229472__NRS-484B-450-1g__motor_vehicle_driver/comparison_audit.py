"""Independent, source-bound comparison audit for NRS 484B.450(1)(g)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from signal_approach import ASSIGNMENT

WORK = Path(__file__).resolve().parent
PLAN = json.loads((WORK / 'case-plan.json').read_text(encoding='utf-8'))
COMPARISONS = {c['comparison_id']: c for c in PLAN['comparisons']}
VARIABLE = {
    'below_vs_at_30ft': 'nominal_signal_distance_m',
    'at_vs_above_30ft': 'nominal_signal_distance_m',
    'approach_vs_past': 'approach_position',
    'official_vs_unofficial': 'signal_status',
    'park_vs_stop': 'activity',
    'park_vs_stand': 'activity',
    'ordinary_vs_conflict': 'exception',
    'ordinary_vs_law': 'exception',
    'ordinary_vs_officer': 'exception',
    'ordinary_vs_device': 'exception',
}
CONDITIONS = ('approach_relation', 'nominal_signal_distance_m', 'activity',
              'signal_status', 'exception')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, reports, *, protocol_fixture=False):
    plan = COMPARISONS.get(comparison_id)
    if plan is None:
        raise ValueError('unknown exact roadside-signal comparison')
    cases = plan['case_ids']
    if set(reports) != set(cases) or len(reports) != len(cases):
        raise ValueError('missing or extra exact comparison report')
    rows = []
    sources = {}
    for case_id in cases:
        path = Path(reports[case_id])
        report = json.loads(path.read_text(encoding='utf-8'))
        if (report.get('format') != 'worker-delivery-audit' or
                report.get('assignment_id') != ASSIGNMENT or
                report.get('case_id') != case_id):
            raise ValueError('exact delivery audit identity differs')
        if protocol_fixture:
            if report.get('physical_acceptance_claimed') is not False:
                raise ValueError('CPU fixture claims physical acceptance')
        elif not (report.get('passed') is True and
                  report.get('physical_acceptance_claimed') is True and
                  report.get('protocol_fixture_checked') is False):
            raise ValueError('accepted original Native delivery audit required')
        record = report.get('comparison_record')
        if not isinstance(record, dict):
            raise ValueError('original comparison measurement missing')
        if not protocol_fixture and record.get('source_kind') != 'original_native_capture':
            raise ValueError('diagnostic comparison source rejected')
        for key in (*CONDITIONS, 'fixed_source_sha256', 'camera_plan',
                    'duration_s', 'measurement'):
            if key not in record:
                raise ValueError('comparison source field missing: ' + key)
        measured = record['measurement']
        if (not isinstance(measured, dict) or
                measured.get('case_id') != case_id or
                measured.get('frames') != 900 or
                not isinstance(measured.get('terminal_body_front_approach_gap_m'), (int, float))):
            raise ValueError('original 900-frame body approach measurement absent')
        rows.append(record)
        sources[case_id] = {'path': str(path), 'sha256': digest(path),
                            'capture_seal_sha256': report.get('capture_seal_sha256'),
                            'video_sha256': report.get('video_sha256')}
    fixed = ('fixed_source_sha256', 'camera_plan', 'duration_s')
    for key in fixed:
        if rows[0][key] != rows[1][key]:
            raise ValueError('fixed comparison condition differs: ' + key)
    variable = VARIABLE[comparison_id]
    if variable == 'approach_position':
        if (rows[0]['approach_relation'] == rows[1]['approach_relation'] or
                rows[0]['nominal_signal_distance_m'] == rows[1]['nominal_signal_distance_m']):
            raise ValueError('declared approach-side position did not change')
    for key in CONDITIONS:
        if key == variable or (variable == 'approach_position' and key in ('approach_relation', 'nominal_signal_distance_m')):
            if rows[0][key] == rows[1][key]:
                raise ValueError('declared comparison variable did not change: ' + key)
        elif rows[0][key] != rows[1][key]:
            raise ValueError('fixed comparison condition differs: ' + key)
    for index, case_id in enumerate(cases):
        short = case_id.removeprefix(ASSIGNMENT + '__')
        config_path = WORK / ('config.json' if short == 'approach_below_30ft_park'
                              else 'cases/' + short + '/config.json')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        if config['selected_case_id'] != case_id:
            raise ValueError('case config identity differs')
        case = config['case']
        expected = (case['approach_relation'], case['nominal_signal_distance_m'],
                    case['halt_activity'], case['signal_status'],
                    case['exception_context'])
        actual = tuple(rows[index][key] for key in CONDITIONS)
        if actual != expected:
            raise ValueError('comparison record differs from selected case construction')
    return {'format': 'worker-comparison-audit', 'assignment_id': ASSIGNMENT,
            'comparison_id': comparison_id, 'passed': not protocol_fixture,
            'protocol_fixture_checked': protocol_fixture,
            'physical_acceptance_claimed': not protocol_fixture,
            'cases': cases, 'declared_variable': variable,
            'inputs': sources, 'legal_verdict': None,
            'limit': 'Measured source isolation and original pixels still require independent review.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--report', nargs=2, action='append', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, dict(args.report)), indent=2))
