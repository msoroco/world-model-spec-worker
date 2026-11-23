"""Exercise all selected audit paths on source-inventoried CPU fixtures."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUDITOR = HERE / 'native/delivery_audit.py'
OUTPUT = HERE / 'native-audit-v2'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
NEGATIVE_JOIN = 'Original actor/frame/trace join differs at 599'
NEGATIVE_PROVENANCE = 'Original Native audit rejects synthetic fixture'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(group, candidate, mode):
    case = HERE.name + '__' + group
    attempt = ROOT / '.runtime-work' / (
        'c229398-manifestbound-chain-' + group + '-' + candidate + '-compatibility')
    saved = HERE / ('manifestbound-chain-' + group + '-' + candidate + '-saved.log')
    command = [sys.executable, str(AUDITOR), '--case', case,
               '--candidate', candidate, '--attempt', str(attempt), '--saved', str(saved)]
    if mode != 'reject_fixture':
        command.append('--fixture')
    if mode == 'reject_join':
        command.append('--reject-frame-join')
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
    path = OUTPUT / (group + '-' + candidate + '-' + mode + '.log')
    path.write_text(run.stdout + run.stderr)
    if mode == 'positive':
        if run.returncode or not json.loads(run.stdout)['diagnostic_only']:
            raise ValueError('Fixture source audit failed: ' + str(path))
    else:
        expected = NEGATIVE_JOIN if mode == 'reject_join' else NEGATIVE_PROVENANCE
        if run.returncode == 0 or expected not in path.read_text():
            raise ValueError('Fixture negative was not rejected: ' + str(path))
    return {'command': ' '.join(command), 'exit_code': run.returncode,
            'log': str(path.relative_to(HERE)), 'sha256': sha(path)}


def main():
    OUTPUT.mkdir(exist_ok=True)
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    records = []
    for entry in manifest['cases']:
        group = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in CANDIDATES:
            records.append({'case_id': entry['case_id'], 'candidate': candidate,
                            'positive': execute(group, candidate, 'positive'),
                            'reject_join': execute(group, candidate, 'reject_join'),
                            'reject_fixture': execute(group, candidate, 'reject_fixture')})
            print(group, candidate, 'positive and two negatives passed', flush=True)
    proof = {'format': 'c229398-production-capable-source-auditor-cpu-v1',
             'auditor_sha256': sha(AUDITOR), 'diagnostic_only': True,
             'selected_chains': records, 'positive_count': len(records),
             'join_rejections': len(records), 'synthetic_provenance_rejections': len(records),
             'original_native_observed': False, 'physical_acceptance_claimed': False}
    index = HERE / 'native-audit-v2-proof.json'
    index.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'selected_chains': len(records), 'proof_sha256': sha(index)}))


if __name__ == '__main__':
    main()
