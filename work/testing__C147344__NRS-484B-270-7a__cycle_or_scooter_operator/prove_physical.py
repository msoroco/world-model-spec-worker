"""CPU fixture for complete, incomplete and missing motion evidence."""

import argparse
import json
import os
import tempfile
from pathlib import Path


def prove(case_id, kind, output):
    root = Path(__file__).resolve().parent
    plan = json.loads((root / 'case-plan.json').read_text())
    if case_id not in {case['case_id'] for case in plan['cases']}:
        raise ValueError('exact case required')
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('unknown physical diagnostic kind')
    output = Path(output)
    if output.exists():
        raise ValueError('fresh physical diagnostic output required')
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        attempt = Path(temporary)
        config = json.loads((root / 'cases' /
                             case_id.rsplit('__', 1)[1] /
                             'config.json').read_text())
        config['physical_completion'] = {
            'criterion': 'travel_progress',
            'motion_source': 'trace.jsonl',
            'position_key': 'position_m',
            'minimum_progress_m': 10.0,
            'minimum_samples': 600,
            'engineering_tolerances_not_legal': True,
            'context_sources': []}
        (attempt / 'config.json').write_text(json.dumps(config) + '\n')
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True}) + '\n')
        mapping = []
        rows = []
        for index in range(600):
            frame = 1000 + index
            time = index / 20
            mapping.append({'carla_frame': frame, 'time_s': time,
                            'video_frame': index})
            rows.append({'frame': frame, 'time_s': time,
                         'position_m': [0 if kind == 'incomplete_motion'
                                        else index * .05, 0]})
        (attempt / 'video_frames.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in mapping))
        if kind != 'missing_evidence':
            (attempt / 'trace.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in rows))
        base = {'case_id': case_id,
                'target_checks': [{'target': 'diagnostic motion target',
                                   'requested': True, 'measured': True,
                                   'method': 'synthetic CPU fixture',
                                   'tolerance': None, 'matched': True,
                                   'physical_cause_confirmed': False,
                                   'cause_evidence': {}}],
                'diagnostic_fixture': True,
                'physical_acceptance_claimed': False}
        from scenario_pipeline.worker_exchange.native_output import physical_result
        receipt = physical_result(attempt, base)
    expected = {'complete_motion': 'met',
                'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    actual = receipt['physical_checks']['maneuver']['status']
    if actual != expected or receipt['maneuver_completed'] != (expected == 'met'):
        raise ValueError('physical diagnostic outcome differs: ' + actual)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    return {'case_id': case_id, 'kind': kind,
            'expected': expected, 'diagnostic_fixture': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.kind, args.output)))


if __name__ == '__main__':
    main()
