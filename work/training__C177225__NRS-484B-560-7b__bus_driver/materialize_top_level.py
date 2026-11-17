"""Materialize the reference primary as the assignment's portable top-level bundle."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
source = json.loads((folder / 'constructions/reference-primary.json').read_text())
plan = json.loads((folder / 'case-plan.json').read_text())
for item in source['files']:
    path = folder / item['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() != item['content']:
        raise ValueError(f'Existing source differs from pinned primary: {path}')
    if not path.exists():
        path.write_text(item['content'])
construction = dict(source)
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
