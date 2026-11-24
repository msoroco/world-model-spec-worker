"""Copy repaired drafts with saved source-channel restoration into current diagnostics."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'current-diagnostic-manifest.json').read_text())
finalizer = (root / 'native/finalize.py').read_text()
for case in manifest['cases']:
    label = case['case_id'].rsplit('__', 1)[1]
    for entry in [case, *case['candidates']]:
        old = json.loads((root / entry['construction']).read_text())
        files = [file for file in old['files'] if file['path'] == 'finalize.py']
        assert len(files) == 1
        files[0]['content'] = finalizer
        configs = [file for file in old['files'] if file['path'] == 'config.json']
        assert len(configs) == 1
        config = json.loads(configs[0]['content'])
        config['required_atoms'] = ['kin.position', 'kin.heading']
        configs[0]['content'] = json.dumps(config, indent=2) + '\n'
        old['status'] = 'unselected_current_saved_channel_repair_draft'
        path = root / 'current-candidates' / label / entry['id'] / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(old, indent=2) + '\n')
        entry['construction'] = path.relative_to(root).as_posix()
        entry['construction_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
manifest['status'] = 'partial_unselected_current_cpu_diagnostic'
(root / 'current-diagnostic-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
