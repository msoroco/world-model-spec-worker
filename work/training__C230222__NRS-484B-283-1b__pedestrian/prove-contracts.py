"""Pinned conditional curb measurement contracts on retained synthetic sources."""
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
    summary = json.loads((HERE / 'curb-summary.json').read_text())
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join((str(HERE / 'native'), env.get('PYTHONPATH', '')))
    records = []
    for item in summary['records']:
        suffix, case = item['case_suffix'], item['case_id']
        row = plan['requirement_dispositions'][0]
        contract = {'format': 'worker-measurement-contract-v1', 'case_id': case,
            'requirements': [{'disposition_index': 0, 'requirement': row['requirement'],
                              'source': row['source'], 'output_key': 'curb_departure_conditional_margin',
                              'method': 'curb_departure', 'value_type': 'object', 'kind': 'measured',
                              'inputs': ['curb-samples.jsonl', 'curb-context.json', 'road.xodr']}],
            'negative': {'remove': ['curb-samples.jsonl'],
                         'error_contains': 'Missing required source: curb-samples.jsonl'}}
        destination = HERE / 'draft-curb' / suffix
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
        validate(contract, plan['requirement_dispositions'], code, case)
        fixture = Path(item['retained_positive'])
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='curb-contract-') as temporary:
            output = Path(temporary) / 'analysis-report.json'
            success = subprocess.run([sys.executable, str(HERE / 'native/finalize.py'),
                '--attempt', str(fixture), '--output', str(output), '--case-id', case],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            if success.returncode:
                raise RuntimeError('Curb contract positive failed: ' + success.stdout)
            report = json.loads(output.read_text())
            verify_report(contract, report, fixture)
            negative = subprocess.run([sys.executable, str(HERE / 'native/finalize.py'),
                '--attempt', str(fixture.parent / (suffix + '-missing')),
                '--output', str(Path(temporary) / 'negative.json'), '--case-id', case],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            if negative.returncode == 0 or contract['negative']['error_contains'] not in negative.stdout:
                raise RuntimeError('Curb contract missing-source negative did not reject')
        value = report['measurements']['curb_departure_conditional_margin']['value']
        records.append({'case_id': case, 'contract': str((destination / 'measurement-contract.json').relative_to(HERE)),
                        'positive': 'pass', 'missing_source_negative': 'pass',
                        'conditional_yield_relation': value['conditional_yield_relation'],
                        'driver_capability_measured': value['driver_capability_measured'],
                        'accepted_recording_claimed': False})
    (HERE / 'curb-contract-summary.json').write_text(json.dumps({
        'format': 'c230222-curb-contract-proof-v1', 'records': records}, indent=2) + '\n')
    print(json.dumps({'case_contracts': len(records), 'pinned_positives': len(records),
                      'missing_source_negatives': len(records), 'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
