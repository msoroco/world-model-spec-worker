"""Pinned steady-witness measurement contract positives and missing-source negatives."""
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
    code = (HERE / 'native/finalize.py').read_text()
    summary = json.loads((HERE / 'steady-summary.json').read_text())
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join((str(HERE / 'native'), env.get('PYTHONPATH', '')))
    records = []
    for item in summary['records']:
        suffix, case = item['case_suffix'], item['case_id']
        row = plan['requirement_dispositions'][0]
        contract = {'format': 'worker-measurement-contract-v1', 'case_id': case,
            'requirements': [{'disposition_index': 0, 'requirement': row['requirement'],
                              'source': row['source'], 'output_key': 'steady_entry_and_progress',
                              'method': 'steady_entry', 'value_type': 'object', 'kind': 'measured',
                              'inputs': ['steady-samples.jsonl', 'steady-context.json', 'road.xodr']}],
            'negative': {'remove': ['steady-samples.jsonl'],
                         'error_contains': 'Missing required source: steady-samples.jsonl'}}
        destination = HERE / 'draft-steady' / suffix
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
        validate(contract, plan['requirement_dispositions'], code, case)
        fixture = Path(item['retained_positive'])
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='d4-contract-') as temporary:
            output = Path(temporary) / 'analysis-report.json'
            success = subprocess.run([sys.executable, str(HERE / 'native/finalize.py'),
                '--attempt', str(fixture), '--output', str(output), '--case-id', case],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            if success.returncode:
                raise RuntimeError('Steady contract positive failed: ' + success.stdout)
            report = json.loads(output.read_text())
            verify_report(contract, report, fixture)
            negative = subprocess.run([sys.executable, str(HERE / 'native/finalize.py'),
                '--attempt', str(fixture.parent / (suffix + '-missing')),
                '--output', str(Path(temporary) / 'negative.json'), '--case-id', case],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            if negative.returncode == 0 or contract['negative']['error_contains'] not in negative.stdout:
                raise RuntimeError('Steady contract missing-source negative did not reject')
        records.append({'case_id': case, 'contract': str((destination / 'measurement-contract.json').relative_to(HERE)),
                        'positive': 'pass', 'missing_source_negative': 'pass',
                        'entry_relative_to_steady': report['measurements']['steady_entry_and_progress']['value']['entry_relative_to_steady'],
                        'accepted_recording_claimed': False})
    (HERE / 'steady-contract-summary.json').write_text(json.dumps({
        'format': 'c10316-steady-contract-proof-v1', 'records': records}, indent=2) + '\n')
    print(json.dumps({'case_contracts': 2, 'pinned_positives': 2,
                      'missing_source_negatives': 2, 'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
