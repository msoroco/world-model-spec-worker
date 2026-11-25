"""Bind the selected paragraph-(a) requirement to saved source measurements."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    selected = [(index, row) for index, row in enumerate(plan['requirement_dispositions'])
                if row['status'] == 'selected_required']
    if len(selected) != 1:
        raise ValueError('one paragraph-(a) selected requirement required')
    index, row = selected[0]
    for item in plan['cases']:
        suffix = item['case_id'].removeprefix(HERE.name + '__')
        contract = {
            'format': 'worker-measurement-contract', 'case_id': item['case_id'],
            'requirements': [{
                'disposition_index': index, 'requirement': row['requirement'],
                'source': row['source'],
                'output_key': 'observed_paragraph_a_condition',
                'method': 'measure_paragraph_a', 'kind': 'measured',
                'value_type': 'object',
                'inputs': ['original-attempt/source-manifest.json',
                           'original-attempt/native/trace.json']}],
            'negative': {'remove': ['original-attempt/native/trace.json'],
                         'error_contains': 'Missing required source: original-attempt/native/trace.json'},
            'legal_judgment': 'unresolved'}
        path = HERE / 'cases' / suffix / 'measurement-contract.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, indent=2) + '\n')


if __name__ == '__main__':
    build()
