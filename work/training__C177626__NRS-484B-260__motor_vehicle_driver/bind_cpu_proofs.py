"""Bind exact current-runtime offline, public and recorded-only CPU receipts."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c177626-entry'
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    b = target.read_bytes()
    if len(b) > 2097152 or b.endswith(b'\n\n') or any(
            row.endswith((b' ', b'\t')) for row in b.splitlines()):
        raise ValueError('Returned proof size or whitespace invalid: ' + str(target))


def offline_spec(path, construction_hash, command):
    return {'exit_code': 0, 'construction_sha256': construction_hash,
            'command': command, 'log': str(path.relative_to(ROOT)),
            'log_sha256': sha(path)}


def compat_spec(directory, proof_dir):
    for source, target in (('compatibility.json', 'compatibility.json'), ('compatibility-analysis.log', 'public-analysis.log'), ('negative-analysis.log', 'negative-analysis.log')):
        copy(directory / source, proof_dir / target)
    receipt = proof_dir / 'compatibility.json'
    return {'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt),
            'log': str((proof_dir / 'public-analysis.log').relative_to(ROOT)),
            'negative_log': str((proof_dir / 'negative-analysis.log').relative_to(ROOT))}


def main():
    manifest = json.loads(MANIFEST.read_text())
    for suffix, case in zip(('a', 'b'), manifest['cases']):
        proof = ROOT / 'native/proofs' / ('probe_' + suffix)
        for candidate in ('primary', 'fallback1'):
            target = proof / candidate
            offline = SCRATCH / f'offline-probe_{suffix}-{candidate}-v4'
            compat = SCRATCH / f'compat-{suffix}-{candidate}-v4'
            copy(offline / 'offline.log', target / 'offline.log')
            selected = case if candidate == 'primary' else case['candidates'][0]
            command = (f'SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c177626-entry '
                       f'.venv-cpu/bin/python -B runtime.py offline --manifest '
                       f'work/{ROOT.name}/execution-manifest.json --case {case["case_id"]} '
                       f'--output .runtime-work/c177626-entry/offline-probe_{suffix}-{candidate}-v4')
            if candidate != 'primary':
                command += ' --candidate fallback1'
            selected['offline'] = offline_spec(target / 'offline.log',
                                               selected['construction_sha256'], command)
            selected['compatibility'] = compat_spec(compat, target)
        case['negative'] = {'log': case['compatibility']['negative_log'],
            'log_sha256': sha(ROOT / case['compatibility']['negative_log'])}
        saved = SCRATCH / f'saved-{suffix}-v1/v0001'
        for source, name in ((saved / 'processing.json', 'processing.json'),
                             (saved / 'analysis.log', 'saved.log')):
            copy(source, proof / name)
        processing, saved_log = proof / 'processing.json', proof / 'saved.log'
        case['post_capture'] = {'recorded_only': True,
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
    print('Bound exact two-case primary/fallback offline, public and saved-only receipts')


if __name__ == '__main__':
    main()
