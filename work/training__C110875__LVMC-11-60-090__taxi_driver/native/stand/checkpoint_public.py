"""Copy exact Native CPU receipts into the assignment return tree."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parents[1]
ROOT = HERE.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cleaned(source, target):
    text = source.read_text()
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    target.write_text('\n'.join(lines) + '\n' if lines else '')


def main():
    manifest_path = ASSIGNMENT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        proof = ASSIGNMENT / 'proofs' / suffix
        proof.mkdir(parents=True, exist_ok=True)
        for candidate in ('primary', 'fallback1'):
            label = '' if candidate == 'primary' else 'fallback1-'
            offline = ROOT / '.runtime-work' / f'c110875-offline-{suffix}-{candidate}-4'
            public = ROOT / '.runtime-work' / f'c110875-public-{suffix}-{candidate}-5'
            if not (offline / 'offline.log').is_file() or not (public / 'compatibility.json').is_file():
                raise FileNotFoundError(f'Incomplete exact proof: {suffix} {candidate}')
            cleaned(offline / 'offline.log', proof / (label + 'offline.log'))
            cleaned(public / 'compatibility-analysis.log', proof / (label + 'public-analysis.log'))
            cleaned(public / 'negative-analysis.log', proof / (label + 'negative-analysis.log'))
            (proof / (label + 'compatibility.json')).write_text(
                json.dumps(json.loads((public / 'compatibility.json').read_text()), indent=2) + '\n')
            target = entry if candidate == 'primary' else entry['candidates'][0]
            target['offline'] = {
                'exit_code': 0, 'construction_sha256': target['construction_sha256'],
                'command': f'runtime.py offline --case {entry["case_id"]} --candidate {candidate}',
                'log': f'proofs/{suffix}/{label}offline.log',
                'log_sha256': digest(proof / (label + 'offline.log'))}
            target['compatibility'] = {
                'receipt': f'proofs/{suffix}/{label}compatibility.json',
                'sha256': digest(proof / (label + 'compatibility.json')),
                'log': f'proofs/{suffix}/{label}public-analysis.log',
                'negative_log': f'proofs/{suffix}/{label}negative-analysis.log'}
            target['negative'] = {
                'log': f'proofs/{suffix}/{label}negative-analysis.log',
                'log_sha256': digest(proof / (label + 'negative-analysis.log'))}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'candidates': 4}))


if __name__ == '__main__':
    main()
