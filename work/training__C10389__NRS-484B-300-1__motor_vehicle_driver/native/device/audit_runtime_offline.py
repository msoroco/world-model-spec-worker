"""Independently bind C10389 pinned receipts to materialized source files."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]
MANIFEST = HERE / 'draft-execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    manifest = read(MANIFEST)
    proof = read(HERE / 'offline' / 'pinned-runtime-proof.json')
    require(proof['manifest_sha256'] == sha(MANIFEST) and
            len(proof['entries']) == 8 and proof['passed'] is True and
            proof['original_native_observed'] is False and
            proof['delivery_ready'] is False, 'pinned summary')
    seen = set()
    files = 0
    for row in proof['entries']:
        key = row['case_id'], row['candidate_id']
        require(key not in seen, 'duplicate candidate')
        seen.add(key)
        case = next(item for item in manifest['cases']
                    if item['case_id'] == row['case_id'])
        choice = ({'construction': case['construction'],
                   'construction_sha256': case['construction_sha256']}
                  if row['candidate_id'] == 'primary' else
                  next(item for item in case['candidates']
                       if item['id'] == row['candidate_id']))
        path = HERE / choice['construction']
        construction = read(path)
        output = ROOT / row['materialized_dir']
        selection = read(output / 'candidate-selection.json')
        log = (output / 'offline.log').read_text()
        require(sha(path) == choice['construction_sha256'] ==
                row['construction_sha256'] == selection['construction_sha256'] and
                selection['manifest_sha256'] == sha(MANIFEST) and
                selection['case_id'] == row['case_id'] and
                selection['candidate_id'] == row['candidate_id'] and
                sha(output / 'offline.log') == row['log_sha256'] and
                'Ran 3 tests' in log and '\nOK\n' in log and
                row['tests'] == 3 and row['exit_code'] == 0 and
                row['simulation_started'] is False,
                'materialized pinned receipt')
        for item in construction['files']:
            require((output / item['path']).read_text() == item['content'],
                    'materialized file bytes')
            files += 1
    require(len(seen) == 8, 'candidate coverage')
    changed = read(MANIFEST)
    changed['cases'][0]['construction_sha256'] = '0' * 64
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', dir=HERE,
                                     delete=False) as stream:
        negative = Path(stream.name)
        stream.write(json.dumps(changed) + '\n')
    try:
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as folder:
            result = subprocess.run([sys.executable, str(ROOT / 'runtime.py'),
                'offline', '--manifest', str(negative),
                '--case', manifest['cases'][0]['case_id'],
                '--candidate', 'primary', '--output', str(Path(folder) / 'output')],
                cwd=ROOT, capture_output=True, text=True, timeout=30)
            require(result.returncode != 0 and
                    'Candidate construction changed' in result.stderr,
                    'changed construction accepted')
    finally:
        negative.unlink()
    receipt = {'format': 'c10389-device-independent-pinned-audit-v1',
        'materialized_candidates': 8, 'source_files_verified': files,
        'changed_construction_negative_rejected': True,
        'simulation_started': False, 'delivery_ready': False}
    (HERE / 'offline' / 'pinned-runtime-audit.json').write_text(
        json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
