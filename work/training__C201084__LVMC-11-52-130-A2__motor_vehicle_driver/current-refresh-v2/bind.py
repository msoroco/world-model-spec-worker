"""Bind all current-runtime candidate receipts to the eight selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
MANIFEST = PACKAGE / 'execution-manifest.json'
RUNTIME_SHA = '5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.relative_to(PACKAGE).as_posix()


def bind(entry, candidate):
    group = entry['case_id'].rsplit('__', 1)[-1]
    prefix = f'{group}-{candidate}'
    selected = entry if candidate == 'primary' else next(
        row for row in entry['candidates'] if row['id'] == candidate)
    offline = HERE / f'{prefix}-offline.json'
    positive = HERE / f'{prefix}-compatibility.json'
    analysis = HERE / f'{prefix}-analysis.log'
    negative = HERE / f'{prefix}-negative.log'
    saved = HERE / f'{prefix}-saved.json'
    receipt = json.loads(positive.read_text())
    process = json.loads(saved.read_text())
    if not (receipt['runtime_manifest_sha256'] == RUNTIME_SHA
            and receipt['construction_sha256'] == selected['construction_sha256']
            and receipt['candidate_id'] == candidate
            and receipt['negative_log_sha256'] == sha(negative)
            and process['analysis_revision']['runtime_manifest_sha256'] == RUNTIME_SHA
            and process['native_revision']['construction_sha256'] == selected['construction_sha256']
            and process['recorded_only'] is True and process['passed'] is True):
        raise ValueError('Stale current-runtime chain: ' + prefix)
    base = '.venv-cpu/bin/python runtime.py'
    common = f'--manifest work/{PACKAGE.name}/execution-manifest.json --case {entry["case_id"]}'
    selected['offline'] = {
        'command': f'{base} offline {common} --candidate {candidate} --output .runtime-work/c201084-refresh-v2/{prefix}-offline',
        'construction_sha256': selected['construction_sha256'],
        'exit_code': 0, 'log': relative(offline), 'log_sha256': sha(offline),
    }
    selected['compatibility'] = {
        'receipt': relative(positive), 'sha256': sha(positive),
        'log': relative(analysis), 'negative_log': relative(negative),
    }
    selected['negative'] = {'log': relative(negative)}
    selected['saved_processing'] = {'receipt': relative(saved), 'sha256': sha(saved)}
    if candidate == 'primary':
        selected['post_capture'] = {
            'command': (f'{base} process-saved {common} --attempt "$SAVED_ATTEMPT" '
                        '--output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"'),
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': relative(saved), 'test_log_sha256': sha(saved),
        }


def main():
    manifest = json.loads(MANIFEST.read_text())
    if manifest['runtime_manifest_sha256'] != RUNTIME_SHA or len(manifest['cases']) != 8:
        raise ValueError('Wrong active runtime or selected case count')
    for entry in manifest['cases']:
        for candidate in CANDIDATES:
            bind(entry, candidate)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(sha(MANIFEST))


if __name__ == '__main__':
    main()
