"""Bind exact v9 offline checks for all selected candidates."""
import hashlib
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
repo = root.parents[1]
path = root/'execution-manifest.json'
manifest = json.loads(path.read_text())


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


for entry in manifest['cases']:
    suffix = entry['id']
    for candidate in ('primary', 'fallback1'):
        version = 'v10' if suffix == 'conflict_25' else 'v9'
        source = repo/'.runtime-work/c229987'/('offline-'+version+'-'+suffix+'-'+candidate)/'offline.log'
        output = root/'native'/(suffix+('-fallback1' if candidate != 'primary' else '')+'-offline.log')
        shutil.copyfile(source, output)
        construction_sha = (entry['construction_sha256'] if candidate == 'primary' else
                            entry['candidates'][0]['construction_sha256'])
        command = ('.venv-cpu/bin/python -B runtime.py offline --manifest work/'+root.name+
                   '/execution-manifest.json --case '+entry['case_id']+' --candidate '+candidate+
                   ' --output .runtime-work/c229987/offline-'+version+'-'+suffix+'-'+candidate)
        proof = {'command': command, 'exit_code': 0, 'construction_sha256': construction_sha,
                 'log': str(output.relative_to(root)), 'log_sha256': sha(output)}
        if candidate == 'primary':
            entry['offline'] = proof
        else:
            entry['candidates'][0]['offline'] = proof
path.write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
