"""Verify exact CPU comparison isolation and source-bound diagnostic receipts."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIFFERENCES = {
    'stop_sign_comparison_1': {'other_actor_start'},
    'stop_sign_comparison_2': {'requested_stop'},
    'stop_sign_comparison_3': {'entrance_device', 'governing_signal_state'},
}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=DIFFERENCES, required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    plan = read(HERE / 'case-plan.json')
    proposal = read(HERE / 'proposals/cases.json')
    manifest = read(HERE / 'execution-manifest.json')
    comparison = next(c for c in plan['comparisons'] if c['comparison_id'] == args.comparison)
    cases = {c['case_id']: c for c in proposal['cases']}
    entries = {e['case_id']: e for e in manifest['cases']}
    selected = [cases[cid] for cid in comparison['case_ids']]
    expected = set(DIFFERENCES[args.comparison])
    if args.mode == 'negative':
        expected.discard(next(iter(expected)))
    actual = {name for name in selected[0]['variable_assignments']
              if any(c['variable_assignments'][name] != selected[0]['variable_assignments'][name]
                     for c in selected[1:])}
    if actual != expected:
        raise ValueError('Comparison changed undeclared setup variable')
    for case in selected:
        cid = case['case_id']
        entry = entries[cid]
        construction = HERE / entry['construction']
        if sha(construction) != entry['construction_sha256']:
            raise ValueError('Comparison construction changed')
        for key, digest_key in [('offline', 'log_sha256'), ('compatibility', 'sha256'),
                                ('post_capture', 'test_log_sha256')]:
            proof = entry[key]
            name = proof.get('receipt') or proof.get('test_log') or proof.get('log')
            if sha(HERE / name) != proof[digest_key]:
                raise ValueError('Comparison diagnostic proof changed: ' + key)
        if case['recording_description'] != read(construction)['recording_description']:
            raise ValueError('Comparison capture contract changed')
    print(json.dumps({'comparison_id': args.comparison, 'case_ids': comparison['case_ids'],
                      'changed_variables': sorted(actual), 'diagnostic_only': True,
                      'native_or_legal_outcome_claimed': False}))


if __name__ == '__main__':
    main()
