"""Pinned source-value contracts for the unselected d4 prior-entry pair."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    code = (HERE / 'native/finalize_exception.py').read_text()
    summary = json.loads((HERE / 'exception-summary.json').read_text())
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join((str(HERE / 'native'), env.get('PYTHONPATH', '')))
    records = []
    for item in summary['records']:
        suffix, case = item['case_suffix'], item['case_id']
        row = plan['requirement_dispositions'][1]
        contract = {'format': 'worker-measurement-contract-v1', 'case_id': case,
            'requirements': [{'disposition_index': 1, 'requirement': row['requirement'],
                              'source': row['source'], 'output_key': 'prior_entry_exception_source_facts',
                              'method': 'prior_entry_exception', 'value_type': 'object', 'kind': 'measured',
                              'inputs': ['exception-samples.jsonl', 'exception-context.json', 'road.xodr']}],
            'negative': {'remove': ['exception-samples.jsonl'],
                         'error_contains': 'Missing required source: exception-samples.jsonl'}}
        destination = HERE / 'draft-exception' / suffix
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
        validate(contract, plan['requirement_dispositions'], code, case)
        validator_status = 'passed_selected_measurement_requirement'
        fixture = Path(item['retained_positive'])
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='d4-exception-contract-') as temporary:
            output = Path(temporary) / 'analysis-report.json'
            success = subprocess.run([sys.executable, str(HERE / 'native/finalize_exception.py'),
                '--attempt', str(fixture), '--output', str(output), '--case-id', case],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            if success.returncode:
                raise RuntimeError('Prior-entry contract positive failed: ' + success.stdout)
            report = json.loads(output.read_text())
            verify_report(contract, report, fixture)
            negative = subprocess.run([sys.executable, str(HERE / 'native/finalize_exception.py'),
                '--attempt', str(fixture.parent / (suffix + '-missing')),
                '--output', str(Path(temporary) / 'negative.json'), '--case-id', case],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            if negative.returncode == 0 or contract['negative']['error_contains'] not in negative.stdout:
                raise RuntimeError('Prior-entry contract missing-source negative did not reject')
        records.append({'case_id': case, 'contract': str((destination / 'measurement-contract.json').relative_to(HERE)),
                        'validator_status': validator_status,
                        'saved_value_verification': 'pass', 'missing_source_negative': 'pass',
                        'entry_indication': report['measurements']['prior_entry_exception_source_facts']['value']['entry_indication'],
                        'lawful_prior_entry_proven': False, 'accepted_recording_claimed': False})
    (HERE / 'exception-contract-summary.json').write_text(json.dumps({
        'format': 'c10316-prior-entry-contract-proof-v1', 'records': records}, indent=2) + '\n')
    print(json.dumps({'draft_case_contracts': 2, 'pinned_saved_value_positives': 2,
                      'pinned_contract_validations': 2,
                      'missing_source_negatives': 2, 'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
