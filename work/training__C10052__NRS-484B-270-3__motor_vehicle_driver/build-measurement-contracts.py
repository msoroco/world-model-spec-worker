"""Pin the C10052 selected witness row to exact saved synthetic sources."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0, str(HERE/'native'))
from worker_exchange.measurement_contract import validate, verify_report
from finalize import facility_stop_observation


def build():
    plan = json.loads((HERE/'case-plan.json').read_text())
    code = (HERE/'native/finalize.py').read_text()
    output = []
    for draft in plan['cases']:
        suffix = draft['case_id'].rsplit('__', 1)[-1]
        folder = HERE/'draft-facility'/suffix
        requirements = []
        for index, disposition in enumerate(plan['requirement_dispositions']):
            if disposition['status'] != 'selected_required' or draft['case_id'] not in disposition.get('case_ids', []):
                continue
            requirements.append({'disposition_index': index,
                                 'requirement': disposition['requirement'],
                                 'source': disposition['source'],
                                 'output_key': 'facility_stop_observation',
                                 'method': 'facility_stop_observation',
                                 'value_type': 'object', 'kind': 'measured',
                                 'inputs': ['native_samples.jsonl', 'road_geometry.json',
                                            'exception_context.json']})
        contract = {'format': 'worker-measurement-contract-v1',
                    'case_id': draft['case_id'], 'requirements': requirements,
                    'negative': {'remove': ['exception_context.json'],
                                 'error_contains': 'Missing required source: exception_context.json'}}
        validate(contract, plan['requirement_dispositions'], code, draft['case_id'])
        report = {'measurements': {'facility_stop_observation': facility_stop_observation(folder)}}
        verify_report(contract, report, folder)
        (folder/'measurement-contract.json').write_text(json.dumps(contract, indent=2)+'\n')
        (folder/'contract-report.json').write_text(json.dumps(report, indent=2)+'\n')
        output.append({'suffix': suffix, 'requirements': len(requirements),
                       'pinned_contract_validate': True,
                       'pinned_saved_value_verify': True, 'selected': False})
    result = {'format': 'c10052-draft-contract-proof-v1', 'rows': output,
              'scope': 'synthetic occupancy values only; Native designation and exceptions unresolved'}
    (HERE/'draft-facility/contract-summary.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
