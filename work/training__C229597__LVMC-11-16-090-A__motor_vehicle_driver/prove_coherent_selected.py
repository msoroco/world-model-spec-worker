"""Reprove both selected cases after repairing the synthetic motion sources."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'selected-pair-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    records = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in [entry, *entry['candidates']]:
            ident = candidate.get('id', 'primary')
            output = ROOT / '.runtime-work' / f'c229597-coherent-v1-{suffix}-{ident}'
            command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', ident, '--output', str(output),
                       '--library', str(ROOT / 'runtime/pipeline/library'),
                       '--validator', str(ROOT / '.runtime-work/decoder-update16/.lake/build/bin/adapterCheck')]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log = ROOT / '.runtime-work' / f'c229597-coherent-v1-{suffix}-{ident}-command.log'
            log.write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(f'{suffix}/{ident} exit {result.returncode}: {result.stderr[-1500:]}')
            proof = json.loads((output / 'compatibility.json').read_text())
            if not proof['passed'] or proof['construction_sha256'] != candidate['construction_sha256']:
                raise ValueError(f'Changed selected construction: {suffix}/{ident}')
            destination = HERE / 'selected-proofs' / suffix / ident
            destination.mkdir(parents=True, exist_ok=True)
            for source, target in [('compatibility.json', 'compatibility.json'),
                                   ('compatibility-analysis.log', 'analysis.log'),
                                   ('negative-analysis.log', 'negative.log')]:
                shutil.copyfile(output / source, destination / target)
            candidate['compatibility'] = {
                'receipt': str((destination / 'compatibility.json').relative_to(HERE)),
                'sha256': sha(destination / 'compatibility.json'),
                'log': str((destination / 'analysis.log').relative_to(HERE)),
                'negative_log': str((destination / 'negative.log').relative_to(HERE)),
            }
            records.append({'case_id': entry['case_id'], 'candidate_id': ident,
                            'construction_sha256': candidate['construction_sha256'],
                            'receipt_sha256': candidate['compatibility']['sha256'],
                            'fixture_recipe_sha256': proof['fixture_recipe_sha256'],
                            'passed': True, 'synthetic_only': True})
            print(suffix, ident, 'passed', flush=True)
    manifest['status'] = 'selected_pair_coherent_synthetic_cpu_compatibility_passed'
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    index = {'format': 'c229597-coherent-selected-compatibility',
             'manifest_sha256': sha(MANIFEST), 'records': records,
             'software_compatibility_passed': True, 'native_executed': False,
             'delivery_ready': False}
    (HERE / 'coherent-compat-index.json').write_text(json.dumps(index, indent=2) + '\n')
    print('index_sha256', sha(HERE / 'coherent-compat-index.json'))


if __name__ == '__main__':
    main()
