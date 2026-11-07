"""Validate exact C405647 measurement contracts and saved negative path."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    code = (ROOT / 'native/finalize.py').read_text()
    rows = []
    for case in ('witness_1', 'witness_2'):
        case_id = ROOT.name + '__' + case
        contract = json.loads((ROOT / 'draft-measurements' /
                               (case + '-contract.json')).read_text())
        validate(contract, plan['requirement_dispositions'], code, case_id)
        folder = ROOT / 'synthetic-local' / case
        report = json.loads((folder / 'analysis-report.json').read_text())
        verify_report(contract, report, folder)
        with tempfile.TemporaryDirectory(prefix='c405647-contract-') as tmp:
            negative = Path(tmp) / 'missing-source'
            shutil.copytree(folder, negative)
            (negative / 'source-scope.json').unlink()
            result = subprocess.run([sys.executable, str(ROOT / 'native/finalize.py'),
                                     '--attempt', str(negative), '--output',
                                     str(negative / 'new-analysis.json')],
                                    text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            if result.returncode == 0 or contract['negative']['error_contains'] not in result.stdout:
                raise AssertionError('Exact missing-source negative did not reject')
            changed = Path(tmp) / 'changed-source'
            shutil.copytree(folder, changed)
            with (changed / 'actor-frames.jsonl').open('a') as output:
                output.write('{}\n')
            try:
                verify_report(contract, report, changed)
            except ValueError as error:
                assert 'source hash differs' in str(error)
            else:
                raise AssertionError('Changed source hash was accepted')
        rows.append({'case_id': case_id,
                     'contract_sha256': sha(ROOT / 'draft-measurements' /
                                             (case + '-contract.json')),
                     'report_sha256': sha(folder / 'analysis-report.json'),
                     'positive_contract_passed': True,
                     'missing_source_negative_rejected': True,
                     'changed_source_negative_rejected': True})
    return {'passed': True, 'results': rows,
            'scope': 'unselected synthetic saved source contract; no Native or physical proof'}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
