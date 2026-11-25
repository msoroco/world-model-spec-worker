"""Bind already proved review-context constructions into the selected manifest."""

import hashlib
import json
from pathlib import Path
import shlex


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    draft = load(ROOT / 'review-draft-manifest.json')
    selected_path = ROOT / 'execution-manifest.json'
    selected = load(selected_path)
    if [e['case_id'] for e in selected['cases']] != [e['case_id'] for e in draft['cases']]:
        raise ValueError('Selected and staged cases differ')
    proof_root = ROOT / 'review-draft'
    offline = load(proof_root / 'draft-offline-proof-index.json')['receipts']
    compat = load(proof_root / 'draft-compat-proofs/index.json')['receipts']
    saved = load(proof_root / 'draft-saved-proofs/index.json')['receipts']
    physical = load(proof_root / 'draft-physical-proofs/index.json')['receipts']
    by_offline = {(e['case_id'], e['candidate_id']): e for e in offline}
    by_compat = {(e['case_id'], e['candidate_id']): e for e in compat}
    by_saved = {e['case_id']: e for e in saved}
    by_physical = {e['case_id']: e for e in physical}
    if len(by_offline) != 24 or len(by_compat) != 24 or len(by_saved) != 12 or len(by_physical) != 12:
        raise ValueError('Staged proof coverage differs')
    for target, source in zip(selected['cases'], draft['cases']):
        case = source['case_id']
        suffix = case.rsplit('__', 1)[-1]
        target['construction'] = source['construction']
        target['construction_sha256'] = source['construction_sha256']
        target['physical_preparation'] = {'receipt': by_physical[case]['receipt'],
                                          'sha256': by_physical[case]['sha256']}
        for candidate_id, holder in [('primary', target)] + [
                (c['id'], c) for c in target['candidates']]:
            if candidate_id != 'primary':
                staged = next(c for c in source['candidates'] if c['id'] == candidate_id)
                holder['construction'] = staged['construction']
                holder['construction_sha256'] = staged['construction_sha256']
            off = by_offline[(case, candidate_id)]
            comp = by_compat[(case, candidate_id)]
            if off['construction_sha256'] != holder['construction_sha256'] or comp['construction_sha256'] != holder['construction_sha256']:
                raise ValueError('Staged proof construction differs')
            holder['offline'] = {'command': shlex.join(off['command']),
                                 'construction_sha256': off['construction_sha256'],
                                 'exit_code': off['exit_code'], 'log': off['log'],
                                 'log_sha256': off['log_sha256']}
            attempt = REPO / '.runtime-work/c158196-review-compat-all-r2' / (suffix + '-' + candidate_id)
            positive = proof_root / 'draft-compat-proofs' / (suffix + '-' + candidate_id + '-analysis.log')
            negative = proof_root / 'draft-compat-proofs' / (suffix + '-' + candidate_id + '-negative.log')
            positive.write_bytes((attempt / 'compatibility-analysis.log').read_bytes())
            negative.write_bytes((attempt / 'negative-analysis.log').read_bytes())
            receipt = ROOT / comp['log']
            value = load(receipt)
            if sha(positive) != value['log_sha256'] or sha(negative) != value['negative_log_sha256']:
                raise ValueError('Compatibility source log changed')
            holder['compatibility'] = {'receipt': comp['log'], 'sha256': sha(receipt),
                                       'log': str(positive.relative_to(ROOT)),
                                       'negative_log': str(negative.relative_to(ROOT))}
            if candidate_id == 'primary':
                target['negative'] = {'log': str(negative.relative_to(ROOT))}
        post = by_saved[case]
        target['post_capture'] = {'receipt': post['log'], 'sha256': post['log_sha256'],
                                  'log': post['log'], 'test_log': post['log'],
                                  'test_log_sha256': post['log_sha256'],
                                  'test_exit_code': post['exit_code'],
                                  'recorded_only': True,
                                  'command': shlex.join(post['command']),
                                  'feedback_command': 'review saved feedback for ' + case}
    selected_path.write_text(json.dumps(selected, indent=2, ensure_ascii=False) + '\n')
    primary = load(ROOT / draft['cases'][0]['construction'])
    (ROOT / 'construction.json').write_text(json.dumps(primary, indent=2, ensure_ascii=False) + '\n')
    for file in primary['files']:
        if file['path'] == 'config.json':
            (ROOT / 'config.json').write_text(file['content'])
    officer = load(ROOT / draft['cases'][6]['construction'])
    for bundle in (primary, officer):
        for file in bundle['files']:
            if file['path'] in ('saved_finalizer.py', 'officer_reference_saved_finalizer.py',
                                'tests/test_officer_reference_saved_finalizer.py'):
                path = ROOT / file['path']
                path.write_text(file['content'])
    print('selected review-context constructions and proved receipts bound for',
          len(selected['cases']), 'cases')


if __name__ == '__main__':
    main()
