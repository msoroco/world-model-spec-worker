"""Exercise all exact comparison commands on current saved CPU attempts."""

from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from build_gpu_queue import SAVED_PROOFS


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DISPATCH = HERE / 'comparison_dispatch.py'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def saved_sources(case_id):
    proof_name = SAVED_PROOFS[case_id.rsplit('__', 1)[-1]]
    proof_path = HERE / proof_name
    proof = json.loads(proof_path.read_text())
    if proof['case_id'] != case_id or proof['exit_code'] != 0:
        raise ValueError('Comparison selected saved proof differs')
    tokens = shlex.split(proof['command'])
    attempt = Path(tokens[tokens.index('--attempt') + 1])
    output = Path(tokens[tokens.index('--output') + 1])
    return attempt, output / 'v0001' / 'analysis', proof_path


def run():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(dir=scratch) as location:
        for comparison in plan['comparisons']:
            case_id = comparison['comparison_id']
            sources = [saved_sources(name) for name in comparison['case_ids']]
            output = Path(location) / (case_id + '.json')
            command = [sys.executable, str(DISPATCH), '--comparison', case_id]
            for attempt, _, _ in sources:
                command.extend(('--attempt', str(attempt)))
            if case_id == 'yield_release_delay_sweep':
                for _, analysis, _ in sources:
                    command.extend(('--analysis-root', str(analysis)))
            command.extend(('--output', str(output)))
            positive = subprocess.run(command, capture_output=True, text=True)
            if positive.returncode:
                raise ValueError(case_id + ': ' + positive.stderr)
            result = json.loads(output.read_text())
            if result.get('comparison_id') != case_id:
                raise ValueError('Comparison dispatch produced another ID')
            rows.append({'comparison_id': case_id,
                         'case_ids': comparison['case_ids'],
                         'saved_proof_sha256': [digest(source[2]) for source in sources],
                         'report_sha256': digest(output),
                         'exit_code': positive.returncode})
        first = plan['comparisons'][0]
        swapped = [saved_sources(name)[0] for name in reversed(first['case_ids'])]
        negative = subprocess.run([sys.executable, str(DISPATCH), '--comparison',
                                   first['comparison_id'], '--attempt', str(swapped[0]),
                                   '--attempt', str(swapped[1]), '--output',
                                   str(Path(location) / 'negative.json')],
                                  capture_output=True, text=True)
        if negative.returncode == 0 or 'selects another case' not in negative.stderr:
            raise ValueError('Comparison dispatch did not reject swapped attempts')
    proof = {'format': 'worker-exact-comparison-dispatch-proof',
             'manifest_sha256': digest(HERE / 'execution-manifest.json'),
             'case_plan_sha256': digest(HERE / 'case-plan.json'),
             'dispatcher_sha256': digest(DISPATCH),
             'comparisons': rows, 'negative_exit_code': negative.returncode,
             'negative_expected_error': 'selects another case',
             'physical_or_legal_acceptance_claimed': False}
    output = HERE / 'comparison-dispatch-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'comparisons': len(rows), 'proof': str(output.relative_to(ROOT)),
                      'sha256': digest(output)}))


if __name__ == '__main__':
    run()
