"""Bind current-runtime receipts to the canonical selected manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
manifest_path = ROOT / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
tests = json.loads((ROOT / 'selected-runtime-receipts.json').read_text())['tests']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test(label):
    matches = [row for row in tests if row['log'] == 'nov25-selected-' + label + '.log']
    if len(matches) != 1 or matches[0]['exit_code'] != 0 or sha(ROOT / matches[0]['log']) != matches[0]['sha256']:
        raise ValueError('selected test receipt missing or changed: ' + label)
    return matches[0]


def compatibility(entry, suffix, fallback=False):
    stem = suffix + '-fallback-compat' if fallback else suffix + '-compat'
    source = REPO / '.runtime-work/c111329-selected-runtime' / stem
    folder = ROOT / 'cases' / suffix
    prefix = 'selected-fallback1-' if fallback else 'selected-primary-'
    items = [('compatibility.json', prefix + 'receipt.json'),
             ('compatibility-analysis.log', prefix + 'positive.log'),
             ('negative-analysis.log', prefix + 'negative.log')]
    for original, target in items:
        (folder / target).write_bytes((source / original).read_bytes())
    receipt = folder / (prefix + 'receipt.json')
    positive = folder / (prefix + 'positive.log')
    negative = folder / (prefix + 'negative.log')
    proof = json.loads(receipt.read_text())
    candidate = 'fallback1' if fallback else 'primary'
    if (proof['case_id'] != entry['case_id'] or proof['candidate_id'] != candidate or
            proof['construction_sha256'] != entry['construction_sha256'] or
            proof['log_sha256'] != sha(positive) or proof['negative_log_sha256'] != sha(negative)):
        raise ValueError('selected compatibility receipt unbound: ' + stem)
    selected = test(('fallback-compat-' if fallback else 'compat-') + suffix)
    return {'command': selected['command'], 'exit_code': 0,
            'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt),
            'log': str(positive.relative_to(ROOT)),
            'negative_log': str(negative.relative_to(ROOT))}


for entry in manifest['cases']:
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    offline = test('offline-' + suffix)
    entry['offline'] = {'command': offline['command'], 'exit_code': 0,
                        'log': offline['log'], 'log_sha256': offline['sha256'],
                        'construction_sha256': entry['construction_sha256']}
    entry['compatibility'] = compatibility(entry, suffix)
    entry['negative'] = {'log': entry['compatibility']['negative_log'],
                         'expected_error': 'Missing required source: diagonal-source.json',
                         'exit_code': 1}
    saved = test('saved-' + suffix)
    entry['post_capture'] = {'recorded_only': True,
                             'command': saved['command'], 'test_exit_code': 0,
                             'test_log': saved['log'], 'test_log_sha256': saved['sha256']}
    fallback = entry['candidates'][0]
    alternate = test('fallback-offline-' + suffix)
    fallback['offline'] = {'command': alternate['command'], 'exit_code': 0,
                           'log': alternate['log'], 'log_sha256': alternate['sha256'],
                           'construction_sha256': fallback['construction_sha256']}
    fallback['compatibility'] = compatibility(fallback | {'case_id': entry['case_id']},
                                             suffix, fallback=True)

manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
print('canonical selected manifest bound to current-runtime primary, fallback, and saved-only receipts')
