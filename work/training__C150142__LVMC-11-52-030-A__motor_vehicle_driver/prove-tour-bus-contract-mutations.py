"""Reject corrupted source-bound measurements from a pinned saved analysis."""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import verify_report


def prove(case, stage):
    if case not in ('tour_bus_below', 'tour_bus_at', 'tour_bus_above',
                    'tour_bus_no_loading'):
        raise ValueError('Unsupported tour-bus case')
    stage = Path(stage).resolve()
    if REPO / '.runtime-work' not in stage.parents:
        raise ValueError('Saved analysis belongs under .runtime-work')
    if (stage / 'analysis').is_dir():
        stage /= 'analysis'
    contract = json.loads((ROOT / 'selected-primary' / case /
                           'selected-measurement-contracts' / (case + '.json')).read_text())
    report = json.loads((stage / 'analysis-report.json').read_text())
    verify_report(contract, report, stage)
    key = contract['requirements'][0]['output_key']
    source = contract['requirements'][0]['inputs'][0]
    corruptions = (
        ('method', lambda r: r['measurements'][key].__setitem__('method', 'invented')),
        ('empty_value', lambda r: r['measurements'][key].__setitem__('value', {})),
        ('source_hash', lambda r: r['measurements'][key]['sources'].__setitem__(source, '0' * 64)),
        ('missing_measurement', lambda r: r['measurements'].pop(key)),
    )
    rejected = []
    for name, mutate in corruptions:
        changed = copy.deepcopy(report)
        mutate(changed)
        try:
            verify_report(contract, changed, stage)
        except ValueError as exc:
            rejected.append({'mutation': name, 'error': str(exc)})
        else:
            raise AssertionError('Corrupted measurement accepted: ' + name)
    return {'case_id': ROOT.name + '__' + case,
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False,
            'valid_report_passed': True, 'rejected': rejected}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--stage', required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.stage), sort_keys=True))
