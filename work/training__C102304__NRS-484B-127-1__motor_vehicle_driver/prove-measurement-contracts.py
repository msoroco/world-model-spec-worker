"""Pinned positive/negative contract proof for two unselected synthetic drafts."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'runtime'/'pipeline'))
sys.path.insert(0, str(HERE/'native'))
from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report
from finalize import analysis_report


def main():
    plan = json.loads((HERE/'case-plan.json').read_text())
    code = (HERE/'native'/'finalize.py').read_text()
    results = []
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        indices = [i for i, row in enumerate(plan['requirement_dispositions'])
                   if row['status'] == 'selected_required' and case_id in row['case_ids']]
        if len(indices) != 1:
            raise ValueError('Expected one exact selected-required C102304 law clause')
        index = indices[0]
        source = plan['requirement_dispositions'][index]
        contract = {'format': 'worker-measurement-contract-v1', 'case_id': case_id,
                    'requirements': [{'disposition_index': index,
                                      'requirement': source['requirement'],
                                      'source': source['source'],
                                      'output_key': 'moving_following_interval',
                                      'method': 'moving_following_interval',
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': ['native_samples.jsonl', 'following_context.json']}],
                    'negative': {'remove': ['native_samples.jsonl'],
                                 'error_contains': 'Missing required source: native_samples.jsonl'}}
        saved = HERE/'draft-following'/suffix
        (saved/'measurement-contract.json').write_text(json.dumps(contract, indent=2)+'\n')
        validate(contract, plan['requirement_dispositions'], code, case_id)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for name in ('native_samples.jsonl', 'following_context.json'):
                shutil.copy2(saved/name, folder/name)
            report = analysis_report(folder, contract)
            verify_report(contract, report, folder)
            (saved/'analysis-report.json').write_text(json.dumps(report, indent=2)+'\n')
            (folder/'native_samples.jsonl').unlink()
            try:
                analysis_report(folder, contract)
            except ValueError as error:
                if contract['negative']['error_contains'] not in str(error):
                    raise
            else:
                raise AssertionError('Missing original samples accepted')
        results.append({'case_id': case_id,
                        'measured_gap_m': report['measurements']['moving_following_interval']['value']['median_bumper_gap_m'],
                        'positive': 'passed', 'missing_source': 'rejected'})
    print(json.dumps({'selected_delivery_cases': 0, 'records': results}, sort_keys=True))


if __name__ == '__main__':
    main()
