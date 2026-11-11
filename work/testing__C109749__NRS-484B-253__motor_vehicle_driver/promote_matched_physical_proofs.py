"""Recheck the matched reciprocal CPU classifier and capture lifecycle fixtures."""
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
manifest_path = folder / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


manifest = json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    suffix = entry['case_id'].split('__')[-1]
    if suffix not in ('reciprocal_yield_matched', 'reciprocal_no_yield'):
        continue
    spec = entry['physical_preparation']
    path = folder / spec['receipt']
    proof = json.loads(path.read_text())
    proof['format'] = 'worker-physical-preparation-fixtures'
    proof['construction_sha256'] = entry['construction_sha256']
    for fixture in proof['fixtures']:
        local_log = path.parent / Path(fixture['log']).name
        local_result = path.parent / Path(fixture['result']).name
        with local_log.open('w') as output:
            subprocess.run(shlex.split(fixture['command']), cwd=repo,
                           stdout=output, stderr=subprocess.STDOUT, check=True)
        fixture['exit_code'] = 0
        fixture['log_sha256'] = sha(local_log)
        fixture['result_sha256'] = sha(local_result)
        fixture['log'] = str(Path('cases') / suffix / fixture['log'])
        fixture['result'] = str(Path('cases') / suffix / fixture['result'])
    life = next(row for row in proof['fixtures'] if row['kind'] == 'lifecycle')
    proof['fixtures'] = [row for row in proof['fixtures'] if row['kind'] != 'lifecycle']
    lifecycle_result = json.loads((folder / life['result']).read_text())
    life['events'] = lifecycle_result['events']
    proof['lifecycle'] = life
    write(path, proof)
    spec['sha256'] = sha(path)
    print(suffix, 'physical preparation promoted', flush=True)
write(manifest_path, manifest)
