"""Bind fresh pinned CPU receipts to the exact delivery manifest."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
MANIFEST = PACKAGE / 'execution-manifest.json'
RUNTIME_SHA = '5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(entry, group, candidate):
    prefix = f'{group}-{candidate}'
    selected = entry if candidate == 'primary' else next(row for row in entry['candidates'] if row['id'] == candidate)
    offline = HERE / f'{prefix}-offline.json'
    positive = HERE / f'{prefix}-compatibility.json'
    analysis = HERE / f'{prefix}-analysis.log'
    negative = HERE / f'{prefix}-negative.log'
    saved = HERE / f'{prefix}-saved.json'
    receipt = json.loads(positive.read_text())
    process = json.loads(saved.read_text())
    if (receipt['runtime_manifest_sha256'] != RUNTIME_SHA or receipt['construction_sha256'] != selected['construction_sha256']
            or process['analysis_revision']['runtime_manifest_sha256'] != RUNTIME_SHA
            or process['native_revision']['construction_sha256'] != selected['construction_sha256']):
        raise ValueError(f'Current pinned proof differs: {prefix}')
    base = '.venv-cpu/bin/python runtime.py'
    common = f'--manifest work/{PACKAGE.name}/execution-manifest.json --case {entry["case_id"]}'
    selected['offline'] = {
        'command': f'{base} offline {common} --candidate {candidate} --output .runtime-work/c229398-selected-current/{prefix}-offline',
        'construction_sha256': selected['construction_sha256'], 'exit_code': 0,
        'log': offline.relative_to(PACKAGE).as_posix(), 'log_sha256': sha(offline),
    }
    selected['compatibility'] = {
        'receipt': positive.relative_to(PACKAGE).as_posix(), 'sha256': sha(positive),
        'log': analysis.relative_to(PACKAGE).as_posix(),
        'negative_log': negative.relative_to(PACKAGE).as_posix(),
    }
    if candidate == 'primary':
        selected['negative'] = {'log': negative.relative_to(PACKAGE).as_posix()}
        selected['saved_processing'] = {'receipt': saved.relative_to(PACKAGE).as_posix(), 'sha256': sha(saved)}
        post = selected['post_capture']
        post['command'] = (f'{base} process-saved {common} --attempt "$SAVED_ATTEMPT" '
                           '--output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"')
        post['test_log'] = saved.relative_to(PACKAGE).as_posix()
        post['test_log_sha256'] = sha(saved)


def main():
    manifest = json.loads(MANIFEST.read_text())
    if manifest['runtime_manifest_sha256'] != RUNTIME_SHA:
        raise ValueError('Manifest does not name active runtime')
    for entry in manifest['cases']:
        group = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            bind(entry, group, candidate)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(sha(MANIFEST))


if __name__ == '__main__':
    main()
