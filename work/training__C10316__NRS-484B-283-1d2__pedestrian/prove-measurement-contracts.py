"""Pinned contract validation, saved-value positives, and missing-source negatives."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report

spec = importlib.util.spec_from_file_location('countdown_finalizer', HERE / 'native/finalize.py')
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    summary = json.loads((HERE / 'draft-countdown-measurement-summary.json').read_text())
    root = Path(summary['retained_root'])
    records = []
    for suffix in ('probe_01', 'probe_02'):
        case_id = next(c['case_id'] for c in plan['cases'] if c['case_id'].endswith(suffix))
        contract = {
            'format': 'worker-measurement-contract-v1', 'case_id': case_id,
            'requirements': [{
                'disposition_index': 0, 'requirement': plan['requirement_dispositions'][0]['requirement'],
                'source': plan['requirement_dispositions'][0]['source'],
                'output_key': 'flashing_countdown_clearance', 'method': 'countdown_clearance',
                'value_type': 'object', 'kind': 'measured',
                'inputs': ['countdown_samples.jsonl', 'countdown-context.json'],
            }],
            'negative': {'remove': ['countdown_samples.jsonl'],
                         'error_contains': 'Missing required source: countdown_samples.jsonl'},
        }
        folder = HERE / 'draft-countdown' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
        validate(contract, plan['requirement_dispositions'], (HERE / 'native/finalize.py').read_text(), case_id)
        fixture = root / suffix
        report = finalizer.report(fixture, case_id)
        values = verify_report(contract, report, fixture)
        (folder / 'analysis-report.json').write_text(json.dumps(report, indent=2) + '\n')
        negative = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10316-countdown-negative-'))
        shutil.copyfile(fixture / 'countdown-context.json', negative / 'countdown-context.json')
        try:
            finalizer.report(negative, case_id)
        except ValueError as error:
            assert contract['negative']['error_contains'] in str(error)
        else:
            raise AssertionError('Missing case source was accepted')
        records.append({'case_id': case_id, 'contract_valid': True,
                        'saved_measurement_verified': bool(values), 'missing_source_rejected': True,
                        'observed_relation': report['measurements']['flashing_countdown_clearance']['value']['clearance_relative_to_displayed_zero']})
    (HERE / 'draft-countdown-contract-summary.json').write_text(json.dumps({
        'format': 'c10316-countdown-unselected-contract-proof-v1', 'records': records,
        'scope': 'synthetic source-bound timing only; no accepted recording or legal verdict'}, indent=2) + '\n')
    print(json.dumps({'pinned_contract_positives': len(records), 'missing_source_negatives': len(records),
                      'selected_cases': 0, 'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
