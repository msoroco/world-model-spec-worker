"""Keep small, source-bound public CPU receipts from ignored diagnostic runs."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep(source, label):
    target = HERE / label
    if source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Returned proof exceeds 2 MiB')
    shutil.copyfile(source, target)
    return {'path': target.name, 'sha256': sha(target)}


def main():
    rows = []
    for case in ('witness1', 'witness2'):
        for candidate in ('primary', 'fallback1'):
            folder = SCRATCH / f'c104538-v2-public-{case}-{candidate}'
            if not (folder / 'compatibility.json').is_file():
                continue
            receipt = json.loads((folder / 'compatibility.json').read_text())
            if receipt.get('passed') is not True or receipt.get('candidate_id') != candidate:
                raise ValueError('Public compatibility did not pass')
            prefix = f'current-v2-{case}-{candidate}'
            rows.append({'case': case, 'candidate': candidate, 'kind': 'compatibility',
                         'receipt': keep(folder / 'compatibility.json', prefix + '-compatibility.json'),
                         'positive_log': keep(folder / 'compatibility-analysis.log', prefix + '-analysis.log'),
                         'negative_log': keep(folder / 'negative-analysis.log', prefix + '-negative.log'),
                         'checks': receipt['checks'],
                         'fixture_sha256': receipt['fixture_sha256'],
                         'measurement_contract_sha256': receipt['measurement_contract_sha256']})
        folder = SCRATCH / f'c104538-v2-saved-{case}-primary-output' / 'v0001'
        if not (folder / 'processing.json').is_file():
            continue
        receipt = json.loads((folder / 'processing.json').read_text())
        if (receipt.get('passed') is not True or receipt.get('missing_evidence') is not False
                or receipt.get('originals_preserved') is not True
                or receipt.get('physical_acceptance_claimed') is not False):
            raise ValueError('Public saved processing did not pass')
        prefix = f'current-v2-{case}-primary'
        rows.append({'case': case, 'candidate': 'primary', 'kind': 'process_saved',
                     'receipt': keep(folder / 'processing.json', prefix + '-processing.json'),
                     'analysis_log': keep(folder / 'analysis.log', prefix + '-saved-analysis.log'),
                     'frames': receipt['timestamp_joins']['frames'],
                     'originals_preserved': True,
                     'missing_evidence': False,
                     'acceptance_claimed': False})
    output = HERE / 'current-v2-public-proof.json'
    output.write_text(json.dumps({'format': 'c104538-unselected-public-v2-cpu-proof',
                                  'manifest_sha256': sha(HERE / 'current-v2-probe-manifest.json'),
                                  'rows': rows,
                                  'scope': 'Synthetic source protocol and software path only; no Native or original sign pixels'},
                                 indent=2) + '\n')
    print(json.dumps({'rows': len(rows), 'proof_sha256': sha(output)}))


if __name__ == '__main__':
    main()
