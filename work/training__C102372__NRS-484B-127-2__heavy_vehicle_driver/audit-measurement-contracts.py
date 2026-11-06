"""Pinned saved-value contract check for unselected truck-gap CPU fixtures."""
import importlib.util
import json
from pathlib import Path
import sys

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline'))
from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report

spec = importlib.util.spec_from_file_location('measure_gap', FOLDER / 'native/measure_gap.py')
measurement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurement)
fixture_spec = importlib.util.spec_from_file_location('c102372_synthetic_gap', FOLDER / 'prove-synthetic-gap.py')
fixture = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture)


def main():
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    results = {}
    for case in ('probe_1', 'probe_2'):
        case_id = plan['assignment_id'] + '__' + case
        source = fixture.write_case(case)
        contract = {
            'format': 'worker-measurement-contract-v1', 'case_id': case_id,
            'requirements': [{
                'disposition_index': 0, 'requirement': plan['law_id'],
                'source': plan['source_law']['source'], 'output_key': 'truck_following_gap',
                'method': 'measure', 'value_type': 'object', 'kind': 'measured',
                'inputs': ['native_samples.jsonl', 'following_context.json', 'road.xodr']}],
            'negative': {'remove': ['native_samples.jsonl'],
                         'error_contains': 'Missing required source: native_samples.jsonl'}}
        contract_path = FOLDER / 'native' / ('measurement-contract-' + case + '.json')
        contract_path.write_text(json.dumps(contract, indent=2) + '\n')
        validate(contract, plan['requirement_dispositions'],
                 (FOLDER / 'native/measure_gap.py').read_text(), case_id)
        measured = measurement.measure(source)
        report = {'measurements': {'truck_following_gap': {
            'method': 'measure', 'value': measured,
            'sources': measured['source_sha256']}}}
        verify_report(contract, report, source)
        missing = dict(report)
        missing['measurements'] = {'truck_following_gap': {
            'method': 'measure', 'value': measured,
            'sources': {k: v for k, v in measured['source_sha256'].items()
                        if k != 'native_samples.jsonl'}}}
        try:
            verify_report(contract, missing, source)
        except ValueError as error:
            assert 'Measurement sources differ' in str(error)
        else:
            raise AssertionError('Missing source binding passed')
        results[case] = {'relation': measured['relation_to_500ft'],
                         'manifest_sha256': measured['manifest_sha256']}
    print(json.dumps({'passed': True, 'cases': results,
                      'selected_or_physical_claim': False}, sort_keys=True))


if __name__ == '__main__':
    main()
