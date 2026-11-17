"""Materialize the reference primary as the assignment's portable top-level bundle."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
source = json.loads((folder / 'constructions/reference-primary.json').read_text())
plan = json.loads((folder / 'case-plan.json').read_text())
for item in source['files']:
    path = folder / item['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    if item['path'] == 'config.json' and path.exists():
        authored = json.loads(path.read_text())
        selected = json.loads(item['content'])
        if {key: value for key, value in authored.items()
                if key != 'supported_case_ids'} != selected:
            raise ValueError('Top-level config differs from pinned primary beyond case inventory')
        continue
    if path.exists() and path.read_text() != item['content']:
        raise ValueError(f'Existing source differs from pinned primary: {path}')
    if not path.exists():
        path.write_text(item['content'])
construction = dict(source)
for item in construction['files']:
    if item['path'] == 'config.json':
        item['content'] = (folder / 'config.json').read_text()
construction['format'] = 'worker-construction'
construction['measurement_plan'] = {
    'source': 'case-plan.json',
    'requirements': plan['requirement_dispositions'],
    'per_case_contracts': {
        entry['case_id']: entry['measurement_contract']
        for entry in json.loads((folder / 'execution-manifest.json').read_text())['cases']
    }
}
construction['static_checks'] = [
    'four original source cameras at the prospective capture profile',
    'officer direction precedes the response',
    'bus and officer source telemetry aligned with all 600 frames',
    'missing officer or camera source rejects finalization'
]
(folder / 'construction.json').write_text(json.dumps(construction, indent=2, ensure_ascii=False) + '\n')
print('top-level reference primary materialized')
