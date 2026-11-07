"""Independently verify retained exception contracts and their CPU reports."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report  # noqa: E402


def audit():
    plan = json.loads((HERE.parent / 'case-plan.json').read_text())
    assert plan['requirement_dispositions'][1]['status'] == 'exception_pending'
    shadow = [dict(row) for row in plan['requirement_dispositions']]
    shadow[1]['status'] = 'selected_required'
    code = (HERE / 'finalize.py').read_text()
    count = 0
    for case in ('exception_1_1', 'exception_1_2'):
        case_id = HERE.parent.name + '__' + case
        contract = json.loads((HERE / 'measurement-contracts' / (case + '.json')).read_text())
        validate(contract, shadow, code, case_id)
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            fixture = HERE / 'saved-fixtures' / case / candidate
            report = json.loads((fixture / 'analysis-report.json').read_text())
            assert report['case_id'] == case_id and not report['selected']
            assert not report['physical_acceptance_claimed'] and not report['legal_verdict_claimed']
            verify_report(contract, report, fixture)
            assert contract['negative']['error_contains'] in (
                fixture / 'negative-analysis.log').read_text()
            count += 1
    return {'passed': True, 'case_candidate_measurements': count,
            'authoritative_branch_status': 'exception_pending',
            'shadow_contract_preflight_only': True,
            'physical_or_legal_result_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
