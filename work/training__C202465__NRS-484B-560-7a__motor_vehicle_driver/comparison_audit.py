"""Independent paired rail source-shape comparison; no legal outcome claim."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from finalize import analyze

AID = Path(__file__).resolve().parent.name
PAIRS = {('space_clear', 'space_short'): 'opposite_space',
         ('grade_clear', 'grade_deficit'): 'undercarriage_clearance',
         ('trailing_exact', 'trailing_just_short'): 'trailing_end_15_feet'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(attempt_a, attempt_b, processing_a, processing_b, diagnostic=False):
    a, b = Path(attempt_a).resolve(), Path(attempt_b).resolve()
    receipts = [json.loads(Path(path).read_text()) for path in (processing_a, processing_b)]
    identities = [receipt.get('case_id', '') for receipt in receipts]
    suffixes = tuple(value.removeprefix(AID + '__') for value in identities)
    if suffixes not in PAIRS or identities != [AID + '__' + suffix for suffix in suffixes]:
        raise ValueError('Exact rail comparison cases differ')
    if not all(receipt.get('passed') is True and receipt.get('recorded_only') is True
               for receipt in receipts):
        raise ValueError('Recorded-only paired rail receipt missing')
    if sha(a / 'road.xodr') != sha(b / 'road.xodr'):
        raise ValueError('Fixed rail road differs')
    if (not (a / 'rail-review/rail-geometry.json').is_file() or
            not (b / 'rail-review/rail-geometry.json').is_file() or
            sha(a / 'rail-review/rail-geometry.json') != sha(b / 'rail-review/rail-geometry.json')):
        raise ValueError('Fixed reference rail geometry differs')
    configs = [json.loads((path / 'config.json').read_text()) for path in (a, b)]
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                  'source_actor_ids', 'required_atoms'):
        if configs[0].get(field) != configs[1].get(field):
            raise ValueError('Fixed rail configuration differs: ' + field)
    if diagnostic and any(json.loads((path / 'acquisition-provenance.json').read_text()).get(
            'provenance_kind') != 'synthetic_fixture' for path in (a, b)):
        raise ValueError('Diagnostic rail comparison needs identified fixtures')
    measured = [analyze(path)['measured'] for path in (a, b)]
    context = [analyze(path)['context'] for path in (a, b)]
    branch = PAIRS[suffixes]
    clearances = [item['maximum_trailing_end_clearance_past_reference_rail_m'] for item in measured]
    if not clearances[0] > clearances[1]:
        raise ValueError('Measured trailing-end contrast absent')
    if branch == 'opposite_space':
        if not context[0]['opposite_side_space_before_entry_m'] > context[1]['opposite_side_space_before_entry_m']:
            raise ValueError('Opposite-side space contrast absent')
    elif branch == 'undercarriage_clearance':
        if not context[0]['rail_grade_required_clearance_m'] < context[1]['rail_grade_required_clearance_m']:
            raise ValueError('Undercarriage grade contrast absent')
    else:
        if not (measured[0]['trailing_end_reached_15_feet'] is True and
                measured[1]['trailing_end_reached_15_feet'] is False):
            raise ValueError('15-foot trailing-end boundary contrast absent')
    return {'format': 'c202465-comparison-audit-v1', 'case_ids': identities,
            'diagnostic_fixture': diagnostic, 'fixed_road_sha256': sha(a / 'road.xodr'),
            'deliberate_difference': branch, 'measured_trailing_clearance_m': clearances,
            'attributed_stop_cause_observed': False,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for option in ('attempt-a', 'attempt-b', 'processing-a', 'processing-b', 'output'):
        parser.add_argument('--' + option, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = compare(args.attempt_a, args.attempt_b, args.processing_a,
                     args.processing_b, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_ids': result['case_ids'],
                      'physical_acceptance_claimed': False}))
