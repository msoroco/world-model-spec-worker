"""Validate all exact speed-case measurement contracts with the pinned runtime."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    sys.path.insert(0, str(repo / 'runtime'))
    from scenario_pipeline.worker_exchange.measurement_contract import validate

    plan = json.loads((folder / 'case-plan.json').read_text())
    code = (folder / 'analysis.py').read_text()
    for suffix in ('below', 'equal', 'above'):
        contract = json.loads((folder / 'cases' / suffix / 'measurement-contract.json').read_text())
        rows = validate(contract, plan['requirement_dispositions'], code,
                        contract['case_id'])
        print(suffix, len(rows), 'selected requirement contracts valid')


if __name__ == '__main__':
    main()
