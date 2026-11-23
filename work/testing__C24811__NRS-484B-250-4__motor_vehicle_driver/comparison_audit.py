"""Independent source-bound C24811 comparison audit; reports contrasts, not law outcomes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS = ('ego_stopped_before_entry_observed', 'distinct_other_stopped_earlier_observed',
        'distinct_occupant_inside_at_ego_entry_observed', 'expected_governing_signal_state')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(root, case):
    short = case.rsplit('__', 1)[-1]
    label = 'primary' if short == 'off_stop_earlier_and_occupied' else short
    attempt = root / ('c24811-'+label+'-synthetic')
    report = root / ('c24811-'+label+'-analysis.json')
    data = json.loads(report.read_text())
    if data.get('case_id') != case:
        raise ValueError('Comparison analysis selects another exact case')
    source = data.get('source_report', {})
    for name in ('junction_context.json', 'vehicle_signal_history.jsonl', 'video_frames.jsonl'):
        path = attempt / name
        if not path.is_file() or source.get('sources', {}).get(name) != sha(path):
            raise ValueError('Comparison original source changed: '+name)
    return {'case_id':case,'analysis_sha256':sha(report),
            'source_sha256':source['sources'],
            'observed':{key:source.get(key) for key in KEYS}}


def audit(root):
    plan = json.loads((HERE/'case-plan.json').read_text())
    manifest = json.loads((HERE/'execution-manifest.json').read_text())
    ids = {e['case_id'] for e in manifest['cases']}
    records = {case:load(root,case) for case in ids}
    expected = {'post_stop_priority':('distinct_other_stopped_earlier_observed','distinct_occupant_inside_at_ego_entry_observed'),
                'full_halt':('ego_stopped_before_entry_observed',),
                'inoperative_activation':('expected_governing_signal_state',)}
    results = []
    for comparison in plan['comparisons']:
        name = comparison['comparison_id']
        if name not in expected or not set(comparison['case_ids']) <= ids:
            raise ValueError('Comparison case inventory differs: '+name)
        members = [records[c] for c in comparison['case_ids']]
        varied = {key for key in KEYS if len({str(row['observed'][key]) for row in members}) > 1}
        if varied != set(expected[name]):
            raise ValueError('Comparison contrast or fixed condition changed: '+name+' '+str(sorted(varied)))
        if any(row['observed']['expected_governing_signal_state'] not in ('Off','Green') for row in members):
            raise ValueError('Unknown governing signal state')
        results.append({'comparison_id':name,'case_ids':comparison['case_ids'],
                        'varied_observations':sorted(varied),
                        'analysis_sha256':{r['case_id']:r['analysis_sha256'] for r in members}})
    if len(results) != 3 or set(records) != ids:
        raise ValueError('Independent comparison coverage incomplete')
    return {'format':'worker-c24811-comparison-diagnostic','passed':True,
            'diagnostic_fixture':True,'physical_acceptance_claimed':False,
            'comparisons':results,'source_bound_case_count':len(records)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--selftest',action='store_true')
    args = parser.parse_args()
    result = audit(args.root)
    if args.selftest:
        from tempfile import TemporaryDirectory
        from shutil import copytree
        with TemporaryDirectory(prefix='c24811-comparison-negative-') as temporary:
            fixture = Path(temporary)
            for item in args.root.glob('c24811-*-analysis.json'):
                if item.name.endswith('-fallback1.json') or item.name.endswith('-fallback2.json') or item.name.endswith('-fallback3.json'):
                    continue
                (fixture/item.name).write_bytes(item.read_bytes())
            for item in args.root.glob('c24811-*-synthetic'):
                copytree(item,fixture/item.name,ignore=lambda _dir,names:{n for n in names if n.endswith('.mkv') or n == 'capture'})
            source = fixture/'c24811-primary-synthetic/vehicle_signal_history.jsonl'
            source.write_text(source.read_text()+'{"tampered":true}\n')
            try:
                audit(fixture)
            except ValueError as error:
                if 'Comparison original source changed' not in str(error):
                    raise
            else:
                raise AssertionError('Changed original comparison source accepted')
        result['tampered_original_source_rejected'] = True
    print(json.dumps(result,sort_keys=True))
