"""Bind every one-way statutory topic to the same original-source measurement."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ['road.xodr', 'road-context.json', 'road-review.json',
           'vehicle-pose.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'capture/evidence.jsonl', 'source_context/one_way_designation.txt',
           'source_context/sign_inventory.txt', 'source_context/sign_authority.txt',
           'source_context/sign_erection.txt', 'source_context/sign_governance.txt']


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    for direction in ('designated', 'opposite'):
        case_id = HERE.name + '__' + direction
        rows = []
        for index, disposition in enumerate(plan['requirement_dispositions']):
            if case_id not in disposition['case_ids']:
                continue
            rows.append({'disposition_index': index,
                         'requirement': disposition['requirement'],
                         'source': disposition['source'],
                         'kind': 'measured', 'method': 'measure_one_way_travel',
                         'output_key': 'one_way_travel_' + str(index),
                         'value_type': 'object', 'inputs': SOURCES})
        contract = {'format': 'worker-measurement-contract',
                    'case_id': case_id, 'requirements': rows,
                    'negative': {'remove': ['source_context/sign_inventory.txt'],
                                 'error_contains': 'Missing required source: source_context/sign_inventory.txt'}}
        path = HERE / 'cases' / direction / 'measurement-contract.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'contracts': 2, 'requirements_per_case': len(rows)}))


if __name__ == '__main__':
    main()
