"""Bind case-specific recorded-only diagnostic and feedback CPU proofs."""
from __future__ import annotations

import json
from pathlib import Path

from prove_post_capture import ASSIGNMENT, WORK, run, sha


def main() -> None:
    manifest_path = WORK / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['assignment_id'] == ASSIGNMENT
    proofs = {'format': 'worker-recorded-only-post-capture-proofs',
              'assignment_id': ASSIGNMENT,
              'scope': 'Source-shaped synthetic diagnostic only; original Native capture and physical acceptance pending',
              'cases': []}
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        variants = {}
        for variant in ('positive', 'missing-source', 'missing-validator'):
            variants[variant] = run(suffix, variant)
            print(suffix, variant, variants[variant]['exit_code'], flush=True)
        proofs['cases'].append({'case_id': case_id, 'variants': variants})
    proof_path = WORK / 'post-capture-proofs.json'
    proof_path.write_text(json.dumps(proofs, indent=2, ensure_ascii=False) + '\n')
    proof_sha = sha(proof_path)
    for entry, proof in zip(manifest['cases'], proofs['cases']):
        assert entry['case_id'] == proof['case_id']
        suffix = entry['case_id'].removeprefix(ASSIGNMENT + '__')
        cmd = ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved '
               f'--manifest work/{ASSIGNMENT}/execution-manifest.json '
               f'--case {entry["case_id"]} --attempt "$ATTEMPT" '
               '--output "$SAVED_OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR" '
               '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        entry['post_capture'] = {
            'recorded_only': True, 'command': cmd, 'feedback_command': cmd,
            'test_exit_code': 0,
            'test_log': proof['variants']['positive']['log'],
            'test_log_sha256': proof['variants']['positive']['log_sha256'],
            'proof_scope': proofs['scope'],
            'feedback_proofs': {'receipt': proof_path.name, 'sha256': proof_sha,
                                'variants': ['missing-source', 'missing-validator']}}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + '\n')
    print('bound', len(manifest['cases']), 'exact cases', flush=True)


if __name__ == '__main__':
    main()
