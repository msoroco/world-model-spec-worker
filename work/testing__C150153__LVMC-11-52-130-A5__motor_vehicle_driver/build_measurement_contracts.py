"""Pin each selected witness to the executable saved elevator measurement."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ['reviewed-site/packet.json', 'history.jsonl', 'comparison-context.json']


def build() -> list[str]:
    plan = json.loads((HERE / 'case-plan.json').read_text())
    disposition = plan['requirement_dispositions'][0]
    cases = []
    for case in plan['cases']:
        case_id = case['case_id']
        if case_id not in disposition['case_ids']:
            raise ValueError('Exact case is outside selected witness disposition')
        kind = case_id.removeprefix(HERE.name + '__')
        contract = {'format': 'worker-measurement-contract',
                    'case_id': case_id,
                    'requirements': [{
                        'disposition_index': 0,
                        'requirement': disposition['requirement'],
                        'source': disposition['source'],
                        'output_key': 'observed_elevator_requirement',
                        'method': 'measure_elevator_requirement',
                        'value_type': 'object', 'kind': 'measured',
                        'inputs': SOURCES}],
                    'negative': {'remove': ['reviewed-site/packet.json'],
                                 'error_contains': 'Missing required source: reviewed-site/packet.json'}}
        path = HERE / 'cases' / kind / 'measurement-contract.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, indent=2, sort_keys=True) + '\n')
        cases.append(str(path.relative_to(HERE)))
    return cases


if __name__ == '__main__':
    print('\n'.join(build()))
