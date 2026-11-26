"""Bind each selected pass to its original-source measurement and negative."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('bicycle_pass_wide', 'electric_bicycle_pass_wide',
         'electric_bicycle_pass_narrow')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    for suffix in CASES:
        case_id = HERE.name + '__' + suffix
        index = next(i for i, item in enumerate(plan['requirement_dispositions'])
                     if case_id in item['case_ids'])
        disposition = plan['requirement_dispositions'][index]
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': index,
                'requirement': disposition['requirement'],
                'source': disposition['source'],
                'output_key': 'full_pass', 'method': 'full_pass',
                'kind': 'measured', 'value_type': 'object',
                'inputs': ['participant-poses.jsonl', 'pass-context.json',
                           'trace.jsonl', 'video_frames.jsonl',
                           'capture/evidence.jsonl']}],
            'negative': {'remove': ['pass-context.json'],
                         'error_contains': 'Missing required source: pass-context.json'}}
        (HERE / f'{suffix}-measurement-contract.json').write_text(
            json.dumps(contract, indent=2) + '\n')
    print(json.dumps({'contracts': list(CASES)}))


if __name__ == '__main__':
    main()
