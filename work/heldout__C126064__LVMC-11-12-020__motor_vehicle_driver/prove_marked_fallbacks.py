"""Prove all six exact marked-turn fallback constructions with pinned runtime."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
MANIFEST = ROOT / 'execution-manifest.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)


def prove():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        short = case.rsplit('__', 1)[-1]
        for candidate in entry['candidates']:
            candidate_id = candidate['id']
            stem = short + '-' + candidate_id
            token = uuid4().hex[:10]
            offline = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
                '--case', case, '--candidate', candidate_id,
                '--output', f'.runtime-work/c126064-{stem}-offline-{token}', '--python', PY]
            offline_log = ROOT / (stem + '-offline.log')
            run(offline, offline_log)
            candidate['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                'log': offline_log.name, 'log_sha256': digest(offline_log),
                'construction_sha256': candidate['construction_sha256']}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
            output = REPO / f'.runtime-work/c126064-{stem}-compat-{token}'
            command = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
                '--case', case, '--candidate', candidate_id,
                '--output', str(output.relative_to(REPO)), '--library', 'runtime/library',
                '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
            subprocess.run(command, cwd=REPO, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, text=True, check=True)
            receipt = ROOT / (stem + '-receipt.json')
            negative = ROOT / (stem + '-negative.log')
            shutil.copy2(output / 'compatibility.json', receipt)
            shutil.copy2(output / 'negative-analysis.log', negative)
            proof = json.loads(receipt.read_text())
            if not proof['passed'] or proof['construction_sha256'] != candidate['construction_sha256']:
                raise ValueError('Wrong fallback compatibility proof')
            analysis = ROOT / (short + '-compatibility-analysis.log')
            if not analysis.is_file() or digest(analysis) != proof['log_sha256']:
                analysis = ROOT / (stem + '-analysis.log')
                shutil.copy2(output / 'compatibility-analysis.log', analysis)
            candidate['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
                'log': analysis.name, 'negative_log': negative.name}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
            print(stem, 'exact offline and missing-source compatibility passed', flush=True)
    return {'cases': len(manifest['cases']), 'candidates': sum(len(e['candidates']) for e in manifest['cases'])}


if __name__ == '__main__':
    print(prove())
