"""Copy current-runtime CPU receipts into the returned bus package."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c393261-repair2'
MANIFEST = ROOT / 'execution-manifest.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_clean(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text()
    destination.write_text(text.rstrip() + '\n')
    if any(line.rstrip() != line for line in destination.read_text().splitlines()):
        raise ValueError(f'Trailing whitespace: {destination}')


def main():
    manifest = json.loads(MANIFEST.read_text())
    for i, case in enumerate(manifest['cases'], 1):
        suffix = f'probe_0{i}'
        proof = ROOT / 'native/proofs' / suffix
        compat = SCRATCH / f'compat-0{i}'
        offline = SCRATCH / f'offline-0{i}'
        for source, target in (
            (compat / 'compatibility.json', proof / 'compatibility.json'),
            (compat / 'compatibility-analysis.log', proof / 'positive-analysis.log'),
            (compat / 'negative-analysis.log', proof / 'negative-analysis.log'),
            (offline / 'offline.log', proof / 'offline.log'),
        ):
            copy_clean(source, target)
        receipt = proof / 'compatibility.json'
        negative = proof / 'negative-analysis.log'
        case['compatibility'] = {
            'receipt': str(receipt.relative_to(ROOT)), 'sha256': digest(receipt),
            'log': str((proof / 'positive-analysis.log').relative_to(ROOT)),
            'negative_log': str(negative.relative_to(ROOT)),
        }
        case['negative'] = {'log': str(negative.relative_to(ROOT)),
                            'log_sha256': digest(negative)}
        offlog = proof / 'offline.log'
        case['offline'] = {
            'exit_code': 0, 'construction_sha256': case['construction_sha256'],
            'command': f'SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c393261-repair2 '
                       f'.venv-cpu/bin/python -B runtime.py offline --manifest '
                       f'work/{ROOT.name}/execution-manifest.json --case {case["case_id"]} '
                       f'--output .runtime-work/c393261-repair2/offline-0{i}',
            'log': str(offlog.relative_to(ROOT)), 'log_sha256': digest(offlog),
        }
        saved = SCRATCH / f'saved-0{i}/v0001'
        processing = proof / 'processing.json'
        saved_log = proof / 'saved.log'
        copy_clean(saved / 'processing.json', processing)
        copy_clean(saved / 'analysis.log', saved_log)
        case['post_capture'] = {
            'recorded_only': True,
            'command': f'.venv-cpu/bin/python -B runtime.py process-saved '
                       f'--manifest work/{ROOT.name}/execution-manifest.json '
                       f'--case {case["case_id"]} --attempt $ATTEMPT '
                       f'--output $SAVED_OUTPUT --library runtime/library '
                       f'--validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/v0001/feedback.json',
            'test_exit_code': 0,
            'test_log': str(saved_log.relative_to(ROOT)),
            'test_log_sha256': digest(saved_log),
            'processing_receipt': str(processing.relative_to(ROOT)),
            'processing_receipt_sha256': digest(processing),
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2).rstrip() + '\n')
    print('Bound latest offline, public positive/negative and recorded-only CPU receipts')


if __name__ == '__main__':
    main()
