"""Materialize portable top-level source capture from first exact primary."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
construction = json.loads((ROOT/'native/selected-drafts/other_long/primary/construction.json').read_text())
manifest = json.loads((ROOT/'execution-manifest.json').read_text())
files = []
for item in construction['files']:
    target = ROOT/item['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(item['content'])
    files.append({'path': item['path'], 'source': f'work/{ROOT.name}/{item["path"]}',
                  'content': item['content']})
construction['files'] = files
construction['supported_case_ids'] = [item['case_id'] for item in manifest['cases']]
(ROOT/'construction.json').write_text(json.dumps(construction, indent=2)+'\n')
print(json.dumps({'files': len(files), 'supported_cases': len(manifest['cases'])}))
