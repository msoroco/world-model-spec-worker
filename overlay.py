"""Materialize a source-hashed portable runtime repair without changing baseline."""
import ast
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / 'runtime/main-pipeline-v1'
SOURCE = ROOT / 'work/_shared/runtime-overlay'
OUTPUT = ROOT / '.runtime-work/overlay'
_CACHED = None


def effective_runtime():
    global _CACHED
    from sys import path
    path.insert(0, str(BASELINE / 'scenario_pipeline'))
    from worker_exchange.common import digest, read, sha, tree, within, write

    baseline_manifest = BASELINE / 'SOURCE-MANIFEST.json'
    declared = read(baseline_manifest)['files']
    for relative, checksum in declared.items():
        if sha(within(BASELINE, relative)) != checksum:
            raise ValueError('Frozen runtime changed: ' + relative)
    manifest_path = SOURCE / 'overlay.json'
    if not manifest_path.exists():
        return BASELINE
    signature = (str(BASELINE), str(OUTPUT), sha(baseline_manifest), digest(tree(SOURCE)))
    if _CACHED == signature and OUTPUT.is_dir():
        return OUTPUT
    spec = read(manifest_path)
    if spec.get('format') != 'worker-runtime-overlay-v1' or spec.get('baseline_sha256') != sha(baseline_manifest):
        raise ValueError('Overlay baseline mismatch')
    files = spec.get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('Overlay must declare replacement files')
    expected = {'overlay.json'}
    replacements = {}
    for item in files:
        relative = item['path']
        if not (relative.startswith('scenario_pipeline/traffic_spec_adapter/') or
                relative.startswith('scenario_pipeline/worker_exchange/') or
                relative.startswith('scenario_pipeline/batch_pipeline/') or
                relative.startswith('python/')) or not relative.endswith('.py'):
            raise ValueError('Overlay path is outside portable Python runtime: ' + relative)
        if relative not in declared or item.get('baseline_sha256') != declared[relative]:
            raise ValueError('Overlay original source mismatch: ' + relative)
        replacement = within(SOURCE, relative)
        if sha(replacement) != item.get('replacement_sha256'):
            raise ValueError('Overlay replacement changed: ' + relative)
        ast.parse(replacement.read_text())
        expected.add(relative)
        if relative in replacements:
            raise ValueError('Duplicate overlay source: ' + relative)
        replacements[relative] = replacement
    if set(tree(SOURCE)) != expected:
        raise ValueError('Unlisted overlay file')
    # Recreate the ignored runtime on every invocation. Validation is cheap
    # compared with a compatibility run and prevents a stale materialization.
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BASELINE, OUTPUT)
    new_files = dict(declared)
    for relative, replacement in replacements.items():
        target = within(OUTPUT, relative)
        shutil.copyfile(replacement, target)
        new_files[relative] = sha(target)
    write(OUTPUT / 'SOURCE-MANIFEST.json', {
        'format': 'worker-effective-runtime-v1',
        'baseline_sha256': sha(baseline_manifest),
        'overlay_sha256': sha(manifest_path),
        'files': new_files,
    })
    _CACHED = signature
    return OUTPUT


if __name__ == '__main__':
    print(effective_runtime())
