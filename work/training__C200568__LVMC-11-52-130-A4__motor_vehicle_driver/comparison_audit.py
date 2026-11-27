"""Independently compare the six exact hydrant case pairs."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, a_processing, b_processing, a_audit, b_audit,
          c_processing, c_audit, diagnostic, omit_b):
    plan = read(ROOT / 'case-plan.json')
    comparison = next((item for item in plan['comparisons']
                       if item['comparison_id'] == comparison_id), None)
    if comparison is None or len(comparison['case_ids']) not in (2, 3):
        raise ValueError('Selected comparison identity differs')
    if omit_b:
        raise ValueError('Missing independent B audit')
    audit_paths = [a_audit, b_audit] + ([c_audit] if c_audit else [])
    processing_paths = [a_processing, b_processing] + ([c_processing] if c_processing else [])
    if len(audit_paths) != len(comparison['case_ids']) or len(processing_paths) != len(comparison['case_ids']):
        raise ValueError('Comparison case count differs')
    audits = [read(path) for path in audit_paths]
    saved = [read(path) for path in processing_paths]
    if ([item.get('case_id') for item in audits] != comparison['case_ids'] or
            [item.get('case_id') for item in saved] != comparison['case_ids'] or
            any(item.get('diagnostic_only') is not diagnostic for item in audits) or
            any(item.get('passed') is not True or item.get('missing_evidence') is not False
                for item in saved)):
        raise ValueError('Independent case audits or saved receipts differ')
    stages = [Path(item['analysis_directory']) for item in saved]
    configs = [read(path / 'config.json') for path in stages]
    reports = [read(path / 'analysis-report.json') for path in stages]
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras', 'frozen_cell'):
        if configs[0][key] != configs[1][key]:
            raise ValueError('Fixed comparison condition differs: ' + key)
    if any(report.get('legal_verdict_claimed') is not False for report in reports):
        raise ValueError('Legal verdict claimed without original review')
    measured = [report['measurements']['hydrant_clearance_ft']['value'] for report in reports]
    thresholds = [report['measurements']['hydrant_clearance_ft']['applicable_threshold_ft']
                  for report in reports]
    deliberate = comparison['deliberate_differences']
    if deliberate == ['hydrant_parking_clearance'] and measured[0] == measured[1]:
        raise ValueError('Requested clearance comparison did not vary')
    if deliberate == ['parallel_hydrant_clearance'] or deliberate == ['angle_or_prohibited_hydrant_clearance']:
        if measured != sorted(measured) or len(set(measured)) != 3 or len(set(thresholds)) != 1:
            raise ValueError('Numeric clearance comparison differs')
    if deliberate and deliberate[0].startswith('exception_'):
        values = [read(path / 'config.json')['exception_context'] for path in stages]
        if values[0] == values[1]:
            raise ValueError('Exception context did not vary')
    return {'format': 'c200568-independent-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'fixed_conditions': comparison['fixed_conditions'],
            'deliberate_differences': deliberate,
            'measured_clearance_ft': measured, 'applicable_threshold_ft': thresholds,
            'saved_processing_sha256': [sha(path) for path in processing_paths],
            'delivery_audit_sha256': [sha(path) for path in audit_paths],
            'diagnostic_only': diagnostic, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    for name in ('comparison_id', 'a_processing', 'b_processing', 'a_audit', 'b_audit', 'output'):
        parser.add_argument('--' + name.replace('_', '-'), required=True)
    parser.add_argument('--c-processing')
    parser.add_argument('--c-audit')
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-b-audit', action='store_true')
    args = parser.parse_args()
    result = audit(args.comparison_id, args.a_processing, args.b_processing,
                   args.a_audit, args.b_audit, args.c_processing, args.c_audit,
                   args.diagnostic, args.omit_b_audit)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain previous comparison audit result')
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_id': args.comparison_id}))


if __name__ == '__main__':
    main()
