"""Source-verified CPU launcher for the pinned v3 runtime and declared repairs.

The repository's frozen launchers still resolve v1. This launcher verifies the
batch-pinned v3 export and materializes only source-hashed Python replacements.
"""
import ast
import fcntl
import hashlib
import json
import os
import runpy
import shutil
import sys
import tempfile
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def runtime():
    batch = json.loads((REPO / 'batch.json').read_text())
    baseline = (REPO / batch['runtime']['root']).resolve()
    manifest = baseline / 'SOURCE-MANIFEST.json'
    baseline_hash = sha(manifest)
    if baseline_hash != batch['runtime']['source_manifest_sha256']:
        raise ValueError('Pinned v3 runtime manifest mismatch')
    declared = json.loads(manifest.read_text())['files']
    for relative, expected in declared.items():
        source = (baseline / relative).resolve()
        if not source.is_relative_to(baseline) or sha(source) != expected:
            raise ValueError('Pinned v3 runtime source mismatch: ' + relative)
    descriptor = REPO / 'work/_shared/runtime-overlay/overlay.json'
    if not descriptor.is_file():
        return baseline
    spec = json.loads(descriptor.read_text())
    if spec.get('format') != 'worker-runtime-overlay-v1' or spec.get('baseline_sha256') != baseline_hash:
        raise ValueError('v3 overlay baseline mismatch')
    if spec.get('bootstrap_sha256') != sha(__file__):
        raise ValueError('v3 overlay bootstrap hash mismatch')
    expected = dict(declared)
    for item in spec['files']:
        relative = item['path']
        if not relative.startswith('scenario_pipeline/') or not relative.endswith('.py') or relative not in declared:
            raise ValueError('Invalid v3 overlay source path: ' + relative)
        if item['baseline_sha256'] != declared[relative]:
            raise ValueError('v3 overlay original source mismatch: ' + relative)
        replacement = (descriptor.parent / relative).resolve()
        if not replacement.is_relative_to(descriptor.parent.resolve()) or sha(replacement) != item['replacement_sha256']:
            raise ValueError('v3 overlay replacement changed: ' + relative)
        ast.parse(replacement.read_text())
        expected[relative] = item['replacement_sha256']
    actual = {str(p.relative_to(descriptor.parent)) for p in descriptor.parent.rglob('*') if p.is_file()}
    if actual != {'overlay.json'} | {item['path'] for item in spec['files']}:
        raise ValueError('Undeclared v3 overlay files')
    work = REPO / '.runtime-work'
    work.mkdir(exist_ok=True)
    output = work / ('runtime-v3-' + sha(descriptor))
    with (work / 'runtime-v3.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if not output.exists():
            temporary = Path(tempfile.mkdtemp(prefix='runtime-v3-build-', dir=work))
            try:
                shutil.copytree(baseline, temporary, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                for item in spec['files']:
                    shutil.copyfile(descriptor.parent / item['path'], temporary / item['path'])
                (temporary / 'SOURCE-MANIFEST.json').write_text(json.dumps({
                    'format': 'worker-effective-runtime-v1', 'baseline_sha256': baseline_hash,
                    'overlay_sha256': sha(descriptor), 'files': expected}, indent=2) + '\n')
                os.replace(temporary, output)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
    effective = json.loads((output / 'SOURCE-MANIFEST.json').read_text())
    if effective.get('files') != expected or effective.get('overlay_sha256') != sha(descriptor):
        raise ValueError('v3 effective runtime manifest changed')
    for relative, checksum in expected.items():
        if sha(output / relative) != checksum:
            raise ValueError('v3 effective runtime source changed: ' + relative)
    return output

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('runtime.py', 'worker_check.py'):
        raise ValueError('Select runtime.py or worker_check.py')
    target, args = sys.argv[1], sys.argv[2:]
    root = runtime()
    sys.path.insert(0, str(root / 'scenario_pipeline'))
    sys.path.insert(1, str(root / 'python'))
    if target == 'runtime.py':
        from worker_exchange.runtime_cli import main as cli
        sys.argv = [str(REPO / target), *args]
        cli()
    else:
        resolver = types.ModuleType('overlay')
        resolver.effective_runtime = lambda: root
        sys.modules['overlay'] = resolver
        sys.argv = [str(REPO / target), *args]
        runpy.run_path(str(REPO / target), run_name='__main__')

if __name__ == '__main__':
    main()
