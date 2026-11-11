"""Rebind all exact compatibility receipts after canonical semantic review."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import time_ns

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    pending = []
    for entry in manifest['cases']:
        case = entry['case_id']
        slug = case.split('__')[-1]
        for candidate, target in [('primary', entry)] + [
                (item['id'], item) for item in entry['candidates']]:
            output = ROOT / '.runtime-work' / (
                'c109705-delivery-compat-' + slug + '-' + candidate + '-' + str(time_ns()))
            command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                       '--manifest', str(MANIFEST), '--case', case,
                       '--candidate', candidate, '--output', str(output),
                       '--library', str(ROOT / 'runtime/library'), '--validator',
                       str(ROOT / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck')]
            base = 'delivery-compat-' + slug + '-' + candidate
            command_log = HERE / 'cases' / (base + '-command.log')
            with command_log.open('w') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log,
                                        stderr=subprocess.STDOUT)
            if result.returncode:
                raise ValueError(base + ' failed: ' + command_log.read_text()[-1200:])
            receipt = json.loads((output / 'compatibility.json').read_text())
            if (receipt.get('passed') is not True or
                    receipt.get('construction_sha256') != target['construction_sha256'] or
                    'negative_case_source' not in receipt.get('checks', [])):
                raise ValueError('Exact compatibility receipt differs: ' + base)
            paths = {}
            for source, suffix in [('compatibility.json', '.json'),
                                   ('compatibility-analysis.log', '-analysis.log'),
                                   ('negative-analysis.log', '-negative.log')]:
                path = HERE / 'cases' / (base + suffix)
                shutil.copy2(output / source, path)
                paths[source] = path
            if (digest(paths['compatibility-analysis.log']) != receipt['log_sha256'] or
                    digest(paths['negative-analysis.log']) != receipt['negative_log_sha256']):
                raise ValueError('Compatibility source logs differ: ' + base)
            pending.append((target, entry, candidate, paths, base))
            print(slug, candidate, 'current semantic compatibility passed', flush=True)
    for target, entry, candidate, paths, base in pending:
        target['compatibility'] = {
            'receipt': str(paths['compatibility.json'].relative_to(HERE)),
            'sha256': digest(paths['compatibility.json']),
            'log': str(paths['compatibility-analysis.log'].relative_to(HERE)),
            'negative_log': str(paths['negative-analysis.log'].relative_to(HERE))}
        if candidate == 'primary':
            entry['negative'] = {
                'log': str(paths['negative-analysis.log'].relative_to(HERE))}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print('canonical manifest:', digest(MANIFEST))


if __name__ == '__main__':
    main()
