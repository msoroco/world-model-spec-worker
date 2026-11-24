"""Bind two fresh recorded-only diagnostic processing runs to source hashes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'selected-draft-execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


cases = []
for suffix in ('reference', 'contrast'):
    attempt = REPO / '.runtime-work' / f'c422978-selected-{suffix}-saved-attempt-v6'
    version = REPO / '.runtime-work' / f'c422978-selected-{suffix}-saved-output-v6/v0001'
    receipt = json.loads((version / 'processing.json').read_text())
    assert receipt['passed'] and receipt['recorded_only']
    assert receipt['originals_preserved'] and receipt['timestamp_joins'] == {
        'frames': 600, 'passed': True, 'missing_original_trace_or_map': False}
    assert receipt['final_video_checks']['passed']
    assert not receipt['missing_evidence']
    target = HERE / f'selected-{suffix}-saved-processing.json'
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    analysis = HERE / f'selected-{suffix}-saved-analysis.log'
    analysis.write_bytes((version / 'analysis.log').read_bytes())
    assert sha(analysis) == receipt['analysis_log_sha256']
    cases.append({'case_id': receipt['case_id'], 'candidate_id': 'primary',
                  'attempt': str(attempt.relative_to(REPO)),
                  'original_source_hashes': receipt['original_source_hashes'],
                  'receipt': target.name, 'receipt_sha256': sha(target),
                  'analysis_log': analysis.name, 'analysis_log_sha256': sha(analysis),
                  'result_sha256': receipt['result_sha256'],
                  'command': f'{REPO}/.venv-cpu/bin/python {REPO}/runtime.py process-saved '
                             f'--manifest {MANIFEST} --case {receipt["case_id"]} '
                             f'--attempt {attempt} --output {version.parent} '
                             f'--library {REPO}/runtime/library '
                             f'--validator {REPO}/.runtime-work/c229398-pinned-decoder/.lake/build/bin/adapterCheck'})
proof = {'format': 'c422978-selected-recorded-only-cpu-proof-v1',
         'selected_manifest_sha256': sha(MANIFEST), 'cases': cases,
         'original_native_observed': False, 'physical_acceptance_claimed': False,
         'legal_acceptance_claimed': False}
(HERE / 'selected-saved-proof.json').write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
print(json.dumps({'cases': len(cases), 'manifest_sha256': proof['selected_manifest_sha256']}))
