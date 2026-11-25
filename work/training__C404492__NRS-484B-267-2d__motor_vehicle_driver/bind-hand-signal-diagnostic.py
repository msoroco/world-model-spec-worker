"""Retain exact current-runtime public and recorded-only hand-signal receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__preparing_hand_signal'
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def copy_text(source, target):
    text = source.read_text().rstrip() + '\n'
    if len(text.encode()) > 2 * 1024 * 1024:
        raise ValueError('Returned receipt exceeds 2 MiB: ' + str(source))
    if any(line.rstrip() != line for line in text.splitlines()):
        raise ValueError('Returned receipt has trailing whitespace: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def main():
    probe = read(HERE / 'current-hand-signal-probe-manifest.json')['cases'][0]
    public_rows = []
    saved_rows = []
    for name in CANDIDATES:
        source = ROOT / '.runtime-work' / ('c404492-hand-public-' + name + '-v2')
        public = read(source / 'compatibility.json')
        expected = (probe['construction_sha256'] if name == 'primary' else
                    next(item['construction_sha256'] for item in probe['candidates']
                         if item['id'] == name))
        if (public.get('case_id') != CASE or public.get('candidate_id') != name
                or public.get('construction_sha256') != expected
                or public.get('passed') is not True
                or public.get('negative_removed') != 'vehicle_poses.jsonl'
                or 'negative_case_source' not in public.get('checks', [])):
            raise ValueError('Hand signal public receipt differs: ' + name)
        target = HERE / 'current-hand-signal-public' / name
        for source_name, target_name in (('compatibility.json', 'receipt.json'),
                                         ('compatibility-analysis.log', 'analysis.log'),
                                         ('negative-analysis.log', 'negative.log')):
            copy_text(source / source_name, target / target_name)
        public_rows.append({'candidate_id': name, 'construction_sha256': expected,
                            'receipt_sha256': sha(target / 'receipt.json'),
                            'analysis_log_sha256': sha(target / 'analysis.log'),
                            'negative_log_sha256': sha(target / 'negative.log'),
                            'passed': True})
        saved_source = ROOT / '.runtime-work' / ('c404492-hand-saved-' + name + '-v2') / 'v0001'
        saved = read(saved_source / 'processing.json')
        if (saved.get('case_id') != CASE or saved.get('candidate_id') != name
                or saved.get('passed') is not True
                or saved.get('recorded_only') is not True
                or saved.get('native_revision', {}).get('construction_sha256') != expected
                or saved.get('originals_preserved') is not True):
            raise ValueError('Hand signal saved receipt differs: ' + name)
        saved_target = HERE / 'current-hand-signal-saved' / (name + '.json')
        copy_text(saved_source / 'processing.json', saved_target)
        saved_rows.append({'candidate_id': name, 'construction_sha256': expected,
                           'receipt_sha256': sha(saved_target), 'recorded_only': True,
                           'originals_preserved': True})
    for name, rows in (('public', public_rows), ('saved', saved_rows)):
        path = HERE / ('current-hand-signal-' + name + '-proof.json')
        path.write_text(json.dumps({'format': 'c404492-hand-signal-' + name + '-proof-v1',
                                    'case_id': CASE, 'probe_manifest_sha256':
                                    sha(HERE / 'current-hand-signal-probe-manifest.json'),
                                    'rows': rows, 'diagnostic_only': True},
                                   indent=2, sort_keys=True) + '\n')
        print(json.dumps({'kind': name, 'candidates': len(rows), 'sha256': sha(path)}))


if __name__ == '__main__':
    main()
