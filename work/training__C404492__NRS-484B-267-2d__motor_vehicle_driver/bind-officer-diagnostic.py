"""Return source-bound officer diagnostic receipts after current-runtime CPU runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_text(source, target):
    raw = source.read_text()
    if not raw or any(line.rstrip() != line for line in raw.splitlines()):
        raise ValueError('Generated receipt has trailing whitespace: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(raw.rstrip('\n') + '\n')
    if sha(source) != sha(target):
        raise ValueError('Receipt copy changed source bytes: ' + str(source))


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def main():
    public_rows = []
    saved_rows = []
    for candidate in CANDIDATES:
        public = SCRATCH / ('c404492-officer-public-' + candidate + '-v6')
        saved = SCRATCH / ('c404492-officer-saved-' + candidate + '-v6') / 'v0001'
        pub_dir = HERE / 'current-officer-public' / candidate
        saved_dir = HERE / 'current-officer-saved'
        for source, target in (
            (public / 'compatibility.json', pub_dir / 'receipt.json'),
            (public / 'compatibility-analysis.log', pub_dir / 'analysis.log'),
            (public / 'negative-analysis.log', pub_dir / 'negative.log'),
            (saved / 'processing.json', saved_dir / (candidate + '.json')),
        ):
            copy_text(source, target)
        pub = json.loads((pub_dir / 'receipt.json').read_text())
        save = json.loads((saved_dir / (candidate + '.json')).read_text())
        if (pub.get('passed') is not True or pub.get('candidate_id') != candidate or
                pub.get('negative_log_sha256') != sha(pub_dir / 'negative.log') or
                pub.get('log_sha256') != sha(pub_dir / 'analysis.log')):
            raise ValueError('Officer public receipt incomplete: ' + candidate)
        if (save.get('passed') is not True or save.get('recorded_only') is not True or
                save.get('originals_preserved') is not True or
                save.get('timestamp_joins', {}).get('passed') is not True):
            raise ValueError('Officer saved receipt incomplete: ' + candidate)
        public_rows.append({key: pub[key] for key in (
            'case_id', 'candidate_id', 'construction_sha256', 'runtime_manifest_sha256',
            'fixture_sha256', 'passed', 'checks', 'analysis_sha256',
            'measurement_contract_sha256', 'negative_removed',
            'negative_error_contains', 'negative_log_sha256')})
        public_rows[-1]['full_receipt_sha256'] = sha(pub_dir / 'receipt.json')
        public_rows[-1]['analysis_log_sha256'] = sha(pub_dir / 'analysis.log')
        saved_rows.append({'candidate_id': candidate,
                           'full_receipt_sha256': sha(saved_dir / (candidate + '.json')),
                           'recorded_only': save.get('recorded_only'),
                           'passed': save.get('passed'),
                           'originals_preserved': save.get('originals_preserved'),
                           'timestamp_joins': save.get('timestamp_joins'),
                           'physical_acceptance_claimed': False})
    public_proof = HERE / 'current-officer-public-proof.json'
    saved_proof = HERE / 'current-officer-saved-proof.json'
    write(public_proof, {'format': 'c404492-officer-public-summary-v1',
                         'results': public_rows,
                         'physical_acceptance_claimed': False})
    write(saved_proof, {'format': 'c404492-officer-saved-summary-v1',
                        'results': saved_rows,
                        'physical_acceptance_claimed': False})
    print(json.dumps({'public_proof_sha256': sha(public_proof),
                      'saved_proof_sha256': sha(saved_proof),
                      'candidate_count': len(public_rows)}))


if __name__ == '__main__':
    main()
