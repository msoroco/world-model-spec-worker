"""Validate all six selected exposure measurement contracts with pinned runtime."""

import json
from pathlib import Path

from worker_exchange.measurement_contract import validate


def main():
    root = Path(__file__).resolve().parent
    dispositions = json.loads((root / 'case-plan.json').read_text())['requirement_dispositions']
    code = (root / 'endangerment_finalizer.py').read_text()
    contracts = sorted((root / 'cases').glob('measurement-contract-*.json'))
    if len(contracts) != 6:
        raise ValueError('Six exact exposure contracts required')
    for path in contracts:
        contract = json.loads(path.read_text())
        validate(contract, dispositions, code, contract['case_id'])
        print(path.name, 'validated')


if __name__ == '__main__':
    main()
