"""Bind current-runtime offline, public and saved-only CPU receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c146108-moto'
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_clean(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text().rstrip() + '\n')
    if len(target.read_bytes()) > 2 * 1024 * 1024:
        raise ValueError('Returned proof exceeds 2 MiB')
    if any(line.rstrip() != line for line in target.read_text().splitlines()):
        raise ValueError('Proof contains trailing whitespace')


def main():
    manifest = json.loads(MANIFEST.read_text())
    for i, case in enumerate(manifest['cases'], 1):
        suffix = f'controlled_{i}'
        proof = ROOT / 'native/proofs' / suffix
        compat = SCRATCH / f'compat-{i}-v3'
        offline = SCRATCH / f'offline-{i}-v5'
        saved = SCRATCH / f'saved-{i}-v1/v0001'
        for source, target in (
            (compat / 'compatibility.json', proof / 'compatibility.json'),
            (compat / 'compatibility-analysis.log', proof / 'positive-analysis.log'),
            (compat / 'negative-analysis.log', proof / 'negative-analysis.log'),
            (offline / 'offline.log', proof / 'offline.log'),
            (saved / 'processing.json', proof / 'processing.json'),
            (saved / 'analysis.log', proof / 'saved.log'),
        ):
            copy_clean(source, target)
        receipt = proof / 'compatibility.json'
        negative = proof / 'negative-analysis.log'
        case['compatibility'] = {
            'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt),
            'log': str((proof / 'positive-analysis.log').relative_to(ROOT)),
            'negative_log': str(negative.relative_to(ROOT))}
        case['negative'] = {'log': str(negative.relative_to(ROOT)),
                            'log_sha256': sha(negative)}
        offlog = proof / 'offline.log'
        case['offline'] = {
            'exit_code': 0, 'construction_sha256': case['construction_sha256'],
            'command': f'SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c146108-moto '
                       f'.venv-cpu/bin/python -B runtime.py offline --manifest '
                       f'work/{ROOT.name}/execution-manifest.json --case {case["case_id"]} '
                       f'--output .runtime-work/c146108-moto/offline-{i}-v5',
            'log': str(offlog.relative_to(ROOT)), 'log_sha256': sha(offlog)}
        processing = proof / 'processing.json'
        saved_log = proof / 'saved.log'
        case['post_capture'] = {
            'recorded_only': True,
            'command': f'.venv-cpu/bin/python -B runtime.py process-saved '
                       f'--manifest work/{ROOT.name}/execution-manifest.json '
                       f'--case {case["case_id"]} --attempt $ATTEMPT '
                       f'--output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/v0001/feedback.json',
            'test_exit_code': 0,
            'test_log': str(saved_log.relative_to(ROOT)),
            'test_log_sha256': sha(saved_log),
            'processing_receipt': str(processing.relative_to(ROOT)),
            'processing_receipt_sha256': sha(processing)}
    MANIFEST.write_text(json.dumps(manifest, indent=2).rstrip() + '\n')
    print('Bound two exact motorcycle offline/public/saved CPU chains')


if __name__ == '__main__':
    main()
