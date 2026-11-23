"""Run selected fallback compatibility for both cases on CPU fixtures."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
MANIFEST = P / 'selected-pair-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    records = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in entry['candidates']:
            ident = candidate['id']
            output = ROOT / '.runtime-work' / ('c229597-selected-' + case + '-' + ident + '-v1')
            command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', ident, '--output', str(output),
                       '--library', str(ROOT / 'runtime/pipeline/library'),
                       '--validator', str(ROOT / '.runtime-work/decoder-update16/.lake/build/bin/adapterCheck')]
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log = ROOT / '.runtime-work' / ('c229597-selected-' + case + '-' + ident + '-command.log')
            log.write_text(process.stdout + process.stderr)
            if process.returncode:
                raise RuntimeError(case + '/' + ident + ': ' + process.stderr[-1000:])
            proof = json.loads((output / 'compatibility.json').read_text())
            if (proof['passed'] is not True or proof['candidate_id'] != ident
                    or proof['construction_sha256'] != candidate['construction_sha256']):
                raise ValueError('Fallback receipt differs: ' + case + '/' + ident)
            dest = P / 'selected-proofs' / case / ident
            dest.mkdir(parents=True, exist_ok=True)
            for name, target in [('compatibility.json', 'compatibility.json'),
                                 ('compatibility-analysis.log', 'analysis.log'),
                                 ('negative-analysis.log', 'negative.log')]:
                shutil.copyfile(output / name, dest / target)
            candidate['compatibility'] = {
                'receipt': 'selected-proofs/' + case + '/' + ident + '/compatibility.json',
                'sha256': sha(dest / 'compatibility.json'),
                'log': 'selected-proofs/' + case + '/' + ident + '/analysis.log',
                'negative_log': 'selected-proofs/' + case + '/' + ident + '/negative.log'}
            records.append({'case': case, 'candidate': ident,
                            'receipt_sha256': candidate['compatibility']['sha256'],
                            'speed_increase_mps': proof['measurement_examples']['text_0_motion']['value']['speed_increase_mps']})
            print(case, ident, 'passed', flush=True)
    manifest['status'] = 'selected_pair_cpu_compatibility_passed'
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    (P / 'selected-fallback-index.json').write_text(json.dumps({
        'format': 'c229597-selected-fallback-compatibility-v1',
        'manifest_sha256': sha(MANIFEST), 'records': records,
        'software_compatibility_passed': True, 'native_executed': False,
        'delivery_ready': False}, indent=2) + '\n')
    print(json.dumps({'fallbacks_passed': len(records),
                      'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
