"""Run exact offline and positive/missing-source compatibility per fallback."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'indication-provisional-manifest.json'
PYTHON = str(REPO / '.venv-cpu/bin/python')
VALIDATOR = '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def prove(point):
    stem = 'c126064_indication_offset-' + point
    case = ROOT.name + '__' + stem
    manifest = json.loads(MANIFEST.read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == case)
    proof = {}
    for candidate in entry['candidates']:
        ident = candidate['id']
        output_name = 'c126064-indication-' + point + '-' + ident + '-' + uuid4().hex[:8]
        offline_output = '.runtime-work/' + output_name + '-offline'
        offline = [PYTHON, 'runtime.py', 'offline', '--manifest',
                   str(MANIFEST.relative_to(REPO)), '--case', case,
                   '--candidate', ident, '--output', offline_output,
                   '--python', PYTHON]
        subprocess.run(offline, cwd=REPO, check=True, capture_output=True, text=True)
        offline_log = ROOT / (stem + '-' + ident + '-offline.log')
        shutil.copy2(REPO / offline_output / 'offline.log', offline_log)
        candidate['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                                'log': offline_log.name,
                                'log_sha256': digest(offline_log),
                                'construction_sha256': candidate['construction_sha256']}

        compatibility_output = '.runtime-work/' + output_name + '-compatibility'
        compatibility = [PYTHON, 'runtime.py', 'compatibility', '--manifest',
                         str(MANIFEST.relative_to(REPO)), '--case', case,
                         '--candidate', ident, '--output', compatibility_output,
                         '--library', 'runtime/library', '--validator', VALIDATOR]
        receipt = ROOT / (stem + '-' + ident + '-receipt.json')
        with receipt.open('w') as stream:
            subprocess.run(compatibility, cwd=REPO, stdout=stream,
                           stderr=subprocess.PIPE, check=True, text=True)
        value = json.loads(receipt.read_text())
        if not value['passed'] or value['candidate_id'] != ident:
            raise ValueError('Fallback compatibility did not pass exactly')
        output = REPO / compatibility_output
        common = ROOT / 'c126064-sweep-compat-analysis.log'
        if digest(common) != digest(output / 'compatibility-analysis.log'):
            raise ValueError('Fallback analysis log differs from retained proof')
        negative = ROOT / (stem + '-' + ident + '-negative.log')
        shutil.copy2(output / 'negative-analysis.log', negative)
        if digest(negative) != value['negative_log_sha256']:
            raise ValueError('Fallback missing-source proof differs')
        candidate['compatibility'] = {'receipt': receipt.name,
                                      'sha256': digest(receipt),
                                      'log': common.name,
                                      'negative_log': negative.name}
        proof[ident] = {'offline_sha256': digest(offline_log),
                        'compatibility_sha256': digest(receipt)}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--point', choices=('0000', '0001', '0002'), required=True)
    print(json.dumps(prove(parser.parse_args().point), indent=2))
