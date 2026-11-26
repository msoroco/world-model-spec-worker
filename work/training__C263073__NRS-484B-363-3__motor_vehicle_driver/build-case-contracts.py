"""Bind each selected case to precisely its applicable witness dispositions."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    universal = json.loads((ROOT / 'measurement-contract.json').read_text())
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        included = {i for i, disposition in enumerate(plan['requirement_dispositions'])
                    if case_id in disposition['case_ids']}
        contract = dict(universal)
        contract['requirements'] = [row for row in universal['requirements']
                                    if row['disposition_index'] in included]
        if not contract['requirements']:
            raise ValueError('Selected case has no disposition: ' + suffix)
        (ROOT / ('measurement-contract-' + suffix + '.json')).write_text(
            json.dumps(contract, indent=2) + '\n')
        print(suffix, sorted(included))


if __name__ == '__main__':
    main()
