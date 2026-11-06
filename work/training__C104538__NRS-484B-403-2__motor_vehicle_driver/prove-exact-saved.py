"""Positive/negative saved processing against each exact materialized draft."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize, execution_env
from worker_exchange.measurement_contract import verify_report


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    manifest = FOLDER / 'draft-execution-manifest.json'
    rows = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c104538-exact-saved-') as temporary:
        scratch = Path(temporary)
        for suffix, fixture_name in (('witness_1','straight'), ('witness_2','u_turn')):
            case_id = FOLDER.name + '__' + suffix
            contract_path = FOLDER / ('draft-measurement-contract-' + suffix + '.json')
            contract = json.loads(contract_path.read_text())
            for candidate in ('primary','fallback1','fallback2','fallback3'):
                output = scratch / (suffix + '-' + candidate)
                materialize(manifest, case_id, output, candidate)
                source = FOLDER / 'draft-u-turn-saved' / fixture_name
                for name in ('native_samples.jsonl','video_frames.jsonl','sign-review.json','pixel_review.jsonl'):
                    shutil.copyfile(source / name, output / name)
                shutil.copyfile(source / 'approach-video-fixture.txt', output / 'approach.mkv')
                before = {name: digest(output / name) for name in
                          ('native_samples.jsonl','video_frames.jsonl','sign-review.json','approach.mkv')}
                command = [sys.executable, str(output / 'finalize.py'), '--attempt', str(output),
                           '--output', str(output / 'analysis-report.json')]
                positive = subprocess.run(command, cwd=output, env=execution_env(),
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
                if positive.returncode:
                    raise RuntimeError('Exact positive saved processing failed: ' + positive.stdout)
                report = json.loads((output / 'analysis-report.json').read_text())
                verify_report(contract, report, output)
                if any(digest(output / name) != old for name, old in before.items()):
                    raise AssertionError('Saved processing changed original source')
                (output / 'native_samples.jsonl').unlink()
                negative = subprocess.run([sys.executable, str(output / 'finalize.py'),
                    '--attempt', str(output), '--output', str(output / 'negative-report.json')],
                    cwd=output, env=execution_env(), text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
                if negative.returncode == 0 or contract['negative']['error_contains'] not in negative.stdout:
                    raise AssertionError('Exact missing-source negative did not reject')
                rows.append({'case_id': case_id, 'candidate_id': candidate,
                    'construction_sha256': json.loads((output / 'candidate-selection.json').read_text())['construction_sha256'],
                    'positive_report_sha256': digest(output / 'analysis-report.json'),
                    'positive_contract_verified': True,
                    'missing_native_source_rejected': True,
                    'observed_in_synthetic_fixture': report['measurements']['signed_u_turn']['value']['u_turn_within_governed_region_observed']})
    return {'format': 'c104538-unselected-exact-saved-proof-v1', 'passed': True,
            'rows': rows, 'native_executed': False, 'selected': False,
            'scope': 'exact package saved finalizer and contract only; synthetic text video, no Core/render compatibility'}


if __name__ == '__main__':
    result = prove()
    print(json.dumps(result, indent=2))
