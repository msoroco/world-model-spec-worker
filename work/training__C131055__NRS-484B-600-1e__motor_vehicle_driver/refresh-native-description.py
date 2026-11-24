"""Align selected capture contracts with the original Native runner."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


manifest_path = HERE / 'execution-manifest.json'
manifest = read(manifest_path)
proposal_path = HERE / 'proposals/cases.json'
proposal = read(proposal_path)
by_id = {item['case_id']: item for item in proposal['cases']}
for entry in manifest['cases']:
    for target in (entry, *entry['candidates']):
        path = HERE / target['construction']
        construction = read(path)
        config = next(json.loads(item['content']) for item in construction['files']
                      if item['path'] == 'config.json')
        description = config['recording_description']
        description.setdefault('context_inputs', [])
        limitation = ('CPU fixture is synthetic; original Native measurement and pixels '
                      'require later capture')
        if limitation not in description['limitations']:
            description['limitations'].append(limitation)
        config['recording_description'] = description
        for item in construction['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
        construction['recording_description'] = description
        write(path, construction)
        target['construction_sha256'] = sha(path)
        target['preparation_status'] = 'native_description_reproof_pending'
        for key in ('offline', 'compatibility', 'negative', 'saved_processing',
                    'delivery_diagnostic', 'delivery_acceptance',
                    'physical_preparation', 'post_capture'):
            target.pop(key, None)
    entry['recording_description'] = description
    by_id[entry['case_id']]['recording_description'] = description
write(proposal_path, proposal)
index_path = HERE / 'proposals/semantic-index.json'
index = read(index_path)
index['stages']['cases']['sha256'] = sha(proposal_path)
write(index_path, index)
manifest['status'] = 'partial_native_description_reproof_pending'
write(manifest_path, manifest)
print(json.dumps({'manifest_sha256': sha(manifest_path),
                  'proposal_sha256': sha(proposal_path)}))
