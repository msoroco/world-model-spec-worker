"""Check a source-bound governing-law contrast without deciding legal scope."""
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from authority_source import ASSIGNMENT, check

FIXED = ('vehicle-trace.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair(absent, present, absent_root, present_root):
    absent_id = ASSIGNMENT + '__governing_law_absent'
    present_id = ASSIGNMENT + '__governing_law_present'
    a = check(absent, absent_root, absent_id)
    p = check(present, present_root, present_id)
    for name in FIXED:
        if absent['sources'][name] != present['sources'][name]:
            raise ValueError('Governing-law pair changed fixed subject or frame source: ' + name)
    binding = present['authority_binding']
    if binding['law_text_source'] not in present['sources']:
        raise ValueError('Specific governing law omitted from present source inventory')
    if present['sources'][binding['law_text_source']] != binding['law_text_sha256']:
        raise ValueError('Present law inventory and binding differ')
    return {'format': 'c229977-governing-law-pair-source-check-v1',
            'absent_case_id': a['case_id'], 'present_case_id': p['case_id'],
            'fixed_source_sha256': {name: absent['sources'][name] for name in FIXED},
            'authority_source_bound': True, 'legal_conclusion': None}


def selftest():
    scratch = Path('.runtime-work')
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='c229977-law-pair-', dir=scratch) as folder:
        root = Path(folder)
        for name in (*FIXED, 'authority-context.json'):
            (root / name).write_text('{}\n')
        (root / 'specific-law.txt').write_text('Diagnostic source shape; no legal authority asserted.\n')
        common = {name: sha(root / name) for name in (*FIXED, 'authority-context.json')}
        a = {'case_id': ASSIGNMENT + '__governing_law_absent',
             'authority_kind': 'law', 'sources': dict(common),
             'authority_binding': None, 'legal_conclusion': None,
             'compliance_independently_verified': False}
        law = {'law_citation': 'diagnostic-only', 'law_text_source': 'specific-law.txt',
               'law_text_sha256': sha(root / 'specific-law.txt'),
               'scope_review': 'diagnostic-only'}
        p = {**a, 'case_id': ASSIGNMENT + '__governing_law_present',
             'sources': {**common, 'specific-law.txt': sha(root / 'specific-law.txt')},
             'authority_binding': law}
        pair(a, p, root, root)
        rejected = []
        for name, changed in (
                ('subject', {**p, 'sources': {**p['sources'],
                                             'vehicle-trace.jsonl': '0' * 64}}),
                ('law inventory', {**p, 'sources': common}),
                ('law binding', {**p, 'authority_binding': None}),
                ('legal preclaim', {**p, 'legal_conclusion': 'allowed'})):
            try:
                pair(a, changed, root, root)
            except ValueError:
                rejected.append(name)
            else:
                raise AssertionError('Invalid governing-law pair accepted: ' + name)
        return {'format': 'c229977-governing-law-pair-diagnostic-v1',
                'source_shapes_checked': 2, 'mutations_rejected': rejected,
                'original_law_observed': False, 'legal_conclusion': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--absent')
    parser.add_argument('--present')
    parser.add_argument('--absent-root')
    parser.add_argument('--present-root')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(selftest()))
    else:
        result = pair(json.loads(Path(args.absent).read_text()),
                      json.loads(Path(args.present).read_text()),
                      Path(args.absent_root), Path(args.present_root))
        print(json.dumps(result))
