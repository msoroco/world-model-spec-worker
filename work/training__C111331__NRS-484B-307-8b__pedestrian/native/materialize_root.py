"""Materialize the canonical root entrypoint for the first selected case."""

import json
from pathlib import Path

folder = Path(__file__).resolve().parent.parent
source = json.loads((folder / 'native/native-drafts/condition_a/primary/construction.json').read_text())
ids = [row['case_id'] for row in json.loads((folder / 'case-plan.json').read_text())['cases']]
source['status'] = 'selected_delivery_draft'
for item in source['files']:
    if item['path'] == 'config.json':
        config = json.loads(item['content'])
        config['supported_case_ids'] = ids
        item['content'] = json.dumps(config, indent=2) + '\n'
    target = folder / item['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(item['content'])
(folder / 'construction.json').write_text(json.dumps(source, indent=2) + '\n')
print(json.dumps({'root_case_id': source['case_id'], 'supported_cases': len(ids)}))
