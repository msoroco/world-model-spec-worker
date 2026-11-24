"""Reject a missing raw Native packet for each remaining probe fallback."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c102372-current-saved-probe-remaining'
MANIFEST = HERE / 'draft-execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in path.rglob('*') if p.is_file()}


def main():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    assert ROOT / '.runtime-work' in output_root.parents
    positives = json.loads((HERE / 'current-saved-probe-remaining-proof.json').read_text())
    assert positives['manifest_sha256'] == sha(MANIFEST)
    records = []
    for positive in positives['candidates']:
        case = positive['case_id']
        probe = case.rsplit('__', 1)[-1]
        candidate = positive['candidate_id']
        source = SCRATCH / probe / candidate / 'attempt'
        negative = SCRATCH / probe / candidate / 'missing-native-attempt'
        assert not negative.exists(), 'Retain previous negative; choose new scratch'
        shutil.copytree(source, negative, copy_function=os.link)
        (negative / 'native_samples.jsonl').unlink()
        before = files(negative)
        output = SCRATCH / probe / candidate / 'missing-native-processed'
        cmd = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', case,
               '--attempt', str(negative), '--output', str(output),
               '--library', str(ROOT / 'runtime/pipeline/library'),
               '--validator', str(VALIDATOR)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        log = HERE / ('current-saved-' + probe + '-' + candidate + '-missing-native.log')
        log.write_text(result.stdout + result.stderr)
        assert result.returncode != 0 and files(negative) == before
        feedback_path = output / 'v0001/feedback.json'
        feedback = json.loads(feedback_path.read_text())
        assert 'Missing required source: native_samples.jsonl' in feedback['error']
        assert feedback['native_replay_requested'] is False
        records.append({'case_id': case, 'candidate_id': candidate,
                        'exit_code': result.returncode, 'log_sha256': sha(log),
                        'feedback_sha256': sha(feedback_path),
                        'expected_error': 'Missing required source: native_samples.jsonl',
                        'remaining_source_bytes_preserved': True,
                        'native_replay_requested': False})
    proof = HERE / 'current-saved-probe-remaining-negative-proof.json'
    proof.write_text(json.dumps({'format': 'c102372-current-saved-probe-remaining-negative-v1',
                                 'manifest_sha256': sha(MANIFEST),
                                 'positive_proof_sha256': sha(HERE / 'current-saved-probe-remaining-proof.json'),
                                 'negatives': records,
                                 'physical_observation_claimed': False,
                                 'selected_delivery_claimed': False}, indent=2) + '\n')
    print(json.dumps({'negatives_rejected': len(records), 'proof_sha256': sha(proof)}))


if __name__ == '__main__':
    main()
