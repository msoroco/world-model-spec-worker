"""Replay draft exact compatibility with temporary draft proposal membership.

The selected nine-case package is restored byte-for-byte in finally. These
proofs do not add the draft points to the canonical delivery package.
"""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DRAFT = HERE / 'listener-sweep'
PLAN = HERE / 'case-plan.json'
PROPOSALS = HERE / 'proposals/cases.json'
PY = sys.executable


def main():
    originals = {PLAN: PLAN.read_bytes(), PROPOSALS: PROPOSALS.read_bytes()}
    try:
        PLAN.write_bytes((DRAFT / 'case-plan.json').read_bytes())
        PROPOSALS.write_bytes((DRAFT / 'proposals/cases.json').read_bytes())
        with tempfile.TemporaryDirectory(prefix='c111603-listener-proof-', dir=ROOT / '.runtime-work') as temp:
            fallback_rows = []
            for offset in (2, 4, 6):
                prefix = f'listener-{offset}m'
                case = HERE.name + f'__ped_horn_listener_{offset}m'
                manifest = HERE / f'{prefix}-manifest.json'
                output = Path(temp) / prefix
                command = [PY, 'runtime.py', 'compatibility', '--manifest', str(manifest.relative_to(ROOT)),
                           '--case', case, '--output', str(output.relative_to(ROOT)),
                           '--library', 'runtime/library',
                           '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
                log = HERE / f'{prefix}-draft-compatibility.log'
                with log.open('w') as stream:
                    subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
                receipt = json.loads((output / 'compatibility.json').read_text())
                if receipt['case_id'] != case:
                    raise ValueError('Draft compatibility case identity differs')
                print(case, 'positive_and_missing_source_compatibility_passed', flush=True)
                for number in (1, 2, 3):
                    candidate = f'fallback{number}'
                    offline = Path(temp) / f'{prefix}-{candidate}-offline'
                    offline_command = [PY, 'runtime.py', 'offline', '--manifest',
                        str(manifest.relative_to(ROOT)), '--case', case,
                        '--candidate', candidate, '--output', str(offline.relative_to(ROOT)),
                        '--python', PY]
                    offline_log = HERE / f'{prefix}-{candidate}-offline.log'
                    with offline_log.open('w') as stream:
                        subprocess.run(offline_command, cwd=ROOT, stdout=stream,
                                       stderr=subprocess.STDOUT, check=True)
                    compatible = Path(temp) / f'{prefix}-{candidate}-compat'
                    compat_command = [PY, 'runtime.py', 'compatibility', '--manifest',
                        str(manifest.relative_to(ROOT)), '--case', case,
                        '--candidate', candidate, '--output', str(compatible.relative_to(ROOT)),
                        '--library', 'runtime/library',
                        '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
                    compat_log = HERE / f'{prefix}-{candidate}-compatibility.log'
                    with compat_log.open('w') as stream:
                        subprocess.run(compat_command, cwd=ROOT, stdout=stream,
                                       stderr=subprocess.STDOUT, check=True)
                    receipt_path = HERE / f'{prefix}-{candidate}-receipt.json'
                    analysis_log = HERE / f'{prefix}-{candidate}-analysis.log'
                    negative_log = HERE / f'{prefix}-{candidate}-negative.log'
                    for source, destination in ((compatible / 'compatibility.json', receipt_path),
                                                (compatible / 'compatibility-analysis.log', analysis_log),
                                                (compatible / 'negative-analysis.log', negative_log)):
                        shutil.copy2(source, destination)
                    fallback_rows.append({'case_id': case, 'candidate': candidate,
                        'construction_sha256': next(c['construction_sha256'] for c in
                            json.loads(manifest.read_text())['cases'][0]['candidates'] if c['id']==candidate),
                        'offline_log': offline_log.name,
                        'offline_log_sha256': hashlib.sha256(offline_log.read_bytes()).hexdigest(),
                        'receipt': receipt_path.name,
                        'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                        'analysis_log': analysis_log.name,
                        'negative_log': negative_log.name})
                    print(case, candidate, 'offline_and_compatibility_passed', flush=True)
            (HERE / 'listener-fallback-proof-index.json').write_text(json.dumps({
                'format':'worker-listener-fallback-draft-proofs', 'proofs':fallback_rows,
                'diagnostic_fixture':True, 'physical_acceptance_claimed':False},indent=2)+'\n')
        saved_command = [PY, str(HERE / 'prove_listener_sweep_primary.py')]
        saved_log = HERE / 'listener-sweep-saved-proof.log'
        with saved_log.open('w') as stream:
            subprocess.run(saved_command, cwd=ROOT, stdout=stream,
                           stderr=subprocess.STDOUT, check=True)
        print('three_draft_saved_processing_proofs_passed', flush=True)
    finally:
        for path, content in originals.items():
            path.write_bytes(content)


if __name__ == '__main__':
    main()
