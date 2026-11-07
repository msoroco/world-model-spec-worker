"""Validate both exception measurement contracts against frozen rules."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

from finalize import finalize

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report  # noqa: E402


def run():
    plan = json.loads((HERE.parent / 'case-plan.json').read_text())
    assert plan['requirement_dispositions'][1]['status'] == 'exception_pending'
    # Structural preflight only. The authoritative disposition stays pending.
    shadow_dispositions = [dict(d) for d in plan['requirement_dispositions']]
    shadow_dispositions[1]['status'] = 'selected_required'
    code = (HERE / 'finalize.py').read_text()
    checked = 0
    for case in ('exception_1_1', 'exception_1_2'):
        case_id = HERE.parent.name + '__' + case
        contract = {'format': 'worker-measurement-contract-v1',
                    'case_id': case_id,
                    'requirements': [{'disposition_index': 1,
                                      'requirement': 'NRS-484B-267-1a',
                                      'source': 'NRS 484B.267(1)(a)',
                                      'output_key': 'officer_direction_timing',
                                      'method': 'officer_direction_and_approach_timing',
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': ['source-scope.json', 'actor-frames.jsonl']}],
                    'negative': {'remove': ['source-scope.json'],
                                 'error_contains': 'Missing required source: source-scope.json'}}
        path = HERE / 'measurement-contracts' / (case + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, indent=2) + '\n')
        validate(contract, shadow_dispositions, code, case_id)
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            fixture = HERE / 'saved-fixtures' / case / candidate
            report_path = fixture / 'analysis-report.json'
            if report_path.exists():
                report_path.unlink()
            report = finalize(fixture, report_path)
            verify_report(contract, report, fixture)
            scratch = Path(tempfile.mkdtemp(dir=REPO / '.runtime-work',
                                            prefix='c405647-exception-contract-'))
            for name in ('source-scope.json', 'actor-frames.jsonl'):
                shutil.copyfile(fixture / name, scratch / name)
            (scratch / 'source-scope.json').unlink()
            try:
                finalize(scratch, scratch / 'negative-analysis.json')
            except ValueError as error:
                assert str(error) == contract['negative']['error_contains']
                (fixture / 'negative-analysis.log').write_text(str(error) + '\n')
            else:
                raise AssertionError('Contract negative accepted')
            checked += 1
    return {'passed': True, 'case_candidate_measurements': checked,
            'frozen_validator_shadow_preflight_and_report_verifier': True,
            'authoritative_branch_status': 'exception_pending',
            'physical_or_legal_result_claimed': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
