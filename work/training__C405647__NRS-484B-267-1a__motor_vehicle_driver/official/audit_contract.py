"""Apply the frozen measurement contract validator to all official fixtures."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report  # noqa: E402


def audit():
    plan = json.loads((HERE.parent / 'case-plan.json').read_text())
    code = (HERE / 'finalize.py').read_text()
    checked = 0
    for case in ('official_1', 'official_2'):
        case_id = HERE.parent.name + '__' + case
        contract = json.loads((HERE / 'measurement-contracts' / (case + '.json')).read_text())
        validate(contract, plan['requirement_dispositions'], code, case_id)
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            fixture = HERE / 'saved-fixtures' / case / candidate
            report = json.loads((fixture / 'analysis-report.json').read_text())
            verify_report(contract, report, fixture)
            assert contract['negative']['error_contains'] in (fixture / 'negative-analysis.log').read_text()
            checked += 1
    return {'passed': True, 'case_candidate_measurements': checked,
            'exact_frozen_contract_validator': True,
            'strict_recipe_v2_verified': False, 'physical_claim': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
