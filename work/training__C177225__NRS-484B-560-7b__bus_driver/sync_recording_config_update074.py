"""Keep materialized config recording metadata equal to selected construction."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    for selected in [entry, *entry['candidates']]:
        path = HERE / selected['construction']
        construction = json.loads(path.read_text())
        config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        config['recording_description'] = construction['recording_description']
        config_file['content'] = json.dumps(config, indent=2) + '\n'
        path.write_text(json.dumps(construction, indent=2) + '\n')
        selected['construction_sha256'] = sha(path)
root_config_path = HERE / 'config.json'
root_config = json.loads(root_config_path.read_text())
root_construction_path = HERE / 'construction.json'
root_construction = json.loads(root_construction_path.read_text())
root_config['recording_description'] = root_construction['recording_description']
root_config_path.write_text(json.dumps(root_config, indent=2) + '\n')
root_config_file = next(item for item in root_construction['files'] if item['path'] == 'config.json')
root_config_file['content'] = root_config_path.read_text()
root_construction_path.write_text(json.dumps(root_construction, indent=2) + '\n')
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'selected_constructions': 8, 'manifest_sha256': sha(MANIFEST)}))
