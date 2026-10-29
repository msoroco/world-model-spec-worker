"""Source-verified update002 launcher for frozen runtime.py and worker_check.py.

The frozen resolver imports a baseline regular package before placing the overlay
on sys.path. This wrapper selects an immutable source-hashed runtime, clears those
cached package bindings, and only then executes the requested frozen launcher.
No command allocates or releases a machine, server, or simulation resource.
"""
import fcntl
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ('worker_exchange', 'traffic_spec_adapter', 'batch_pipeline', 'carla_sgg')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def within(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Runtime path escapes its declared root')
    return path


def inputs(repo):
    batch = read(repo / 'batch.json')
    baseline = within(repo, batch['runtime']['root'])
    baseline_manifest = baseline / 'SOURCE-MANIFEST.json'
    baseline_sha = sha(baseline_manifest)
    if baseline_sha != batch['runtime']['source_manifest_sha256']:
        raise ValueError('Bootstrap baseline manifest differs from batch')
    resolver = repo / 'overlay.py'
    if sha(resolver) != batch['frozen_files']['overlay.py']:
        raise ValueError('Bootstrap resolver differs from frozen source')
    declared = read(baseline_manifest)['files']
    for relative, checksum in declared.items():
        if sha(within(baseline, relative)) != checksum:
            raise ValueError('Bootstrap baseline source changed: ' + relative)
    source = repo / 'work/_shared/runtime-overlay'
    descriptor = source / 'overlay.json'
    spec = read(descriptor)
    if spec.get('format') != 'worker-runtime-overlay-v1' or spec.get('baseline_sha256') != baseline_sha:
        raise ValueError('Bootstrap overlay baseline mismatch')
    if spec.get('bootstrap_sha256') != sha(Path(__file__)):
        raise ValueError('Bootstrap source hash differs from overlay declaration')
    expected = dict(declared)
    seen = set()
    for item in spec['files']:
        relative = item['path']
        if relative in seen or relative not in declared or item['baseline_sha256'] != declared[relative]:
            raise ValueError('Bootstrap replacement source identity differs')
        if sha(within(source, relative)) != item['replacement_sha256']:
            raise ValueError('Bootstrap replacement source changed: ' + relative)
        seen.add(relative)
        expected[relative] = item['replacement_sha256']
    if not seen:
        raise ValueError('Bootstrap requires a declared runtime repair')
    expected_source = {'overlay.json'} | seen
    actual_source = {str(p.relative_to(source)) for p in source.rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts}
    if actual_source != expected_source:
        raise ValueError('Bootstrap overlay has undeclared files')
    return baseline, baseline_sha, descriptor, sha(descriptor), expected


def verify_runtime(runtime, baseline_sha, overlay_sha, expected):
    manifest = read(runtime / 'SOURCE-MANIFEST.json')
    if (manifest.get('format') != 'worker-effective-runtime-v1' or
            manifest.get('baseline_sha256') != baseline_sha or
            manifest.get('overlay_sha256') != overlay_sha or manifest.get('files') != expected):
        raise ValueError('Immutable runtime manifest identity differs')
    actual = {str(p.relative_to(runtime)) for p in runtime.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and str(p.relative_to(runtime)) != 'SOURCE-MANIFEST.json'}
    if actual != set(expected):
        raise ValueError('Immutable runtime file inventory differs')
    for relative, checksum in expected.items():
        if sha(within(runtime, relative)) != checksum:
            raise ValueError('Immutable runtime source changed: ' + relative)
    return runtime


def load_resolver(repo, name):
    spec = importlib.util.spec_from_file_location(name, repo / 'overlay.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ROOT.resolve() != repo:
        raise ValueError('Resolver points outside the selected repository')
    return module


def prepare_runtime(repo=ROOT):
    repo = Path(repo).resolve()
    baseline, baseline_sha, descriptor, overlay_sha, expected = inputs(repo)
    work = repo / '.runtime-work'
    work.mkdir(exist_ok=True)
    # A direct child retains the frozen launcher's root.parents[1]/batch.json join.
    immutable = work / ('runtime002-' + overlay_sha)
    with (work / 'runtime002-bootstrap.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if immutable.exists():
            return verify_runtime(immutable, baseline_sha, overlay_sha, expected)
        resolver = load_resolver(repo, '_update002_build_resolver_' + overlay_sha)
        materialized = Path(resolver.effective_runtime()).resolve()
        verify_runtime(materialized, baseline_sha, overlay_sha, expected)
        temporary = Path(tempfile.mkdtemp(prefix='runtime002-build-', dir=work))
        try:
            shutil.copytree(materialized, temporary, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            verify_runtime(temporary, baseline_sha, overlay_sha, expected)
            os.replace(temporary, immutable)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return verify_runtime(immutable, baseline_sha, overlay_sha, expected)


def clear_runtime_modules(repo):
    baseline = repo / 'runtime/main-pipeline-v1'
    default = repo / '.runtime-work/overlay'
    for name, module in list(sys.modules.items()):
        remove = any(name == prefix or name.startswith(prefix + '.') for prefix in PACKAGES)
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            remove = remove or path.is_relative_to(baseline) or path.is_relative_to(default)
            remove = remove or (path.is_relative_to(repo / '.runtime-work') and
                                any(p.startswith('runtime002-') for p in path.relative_to(repo / '.runtime-work').parts))
        if remove:
            sys.modules.pop(name, None)


def activate_runtime(repo, runtime):
    repo = Path(repo).resolve(); runtime = Path(runtime).resolve()
    if runtime.parent != repo / '.runtime-work':
        raise ValueError('Immutable runtime has incompatible repository depth')
    clear_runtime_modules(repo)
    prefixes = [str(runtime / 'scenario_pipeline'), str(runtime / 'python')]
    sys.path[:] = prefixes + [p for p in sys.path if p not in prefixes]
    importlib.invalidate_caches()
    # Both frozen launchers call effective_runtime again. Keep them on the verified
    # immutable child, so they cannot recreate a runtime another process is using.
    resolver = load_resolver(repo, 'overlay')
    resolver.effective_runtime = lambda: runtime
    sys.modules['overlay'] = resolver
    package = importlib.import_module('worker_exchange')
    common = importlib.import_module('worker_exchange.common')
    if not all(Path(module.__file__).resolve().is_relative_to(runtime) for module in (package, common)):
        raise ValueError('Runtime package cache still resolves to baseline sources')
    return {'runtime': str(runtime), 'runtime_manifest_sha256': sha(runtime / 'SOURCE-MANIFEST.json'),
            'bootstrap_sha256': sha(Path(__file__)), 'package_path': list(package.__path__),
            'common_source': str(Path(common.__file__).resolve()), 'immutable': True}


def main(argv=None, repo=ROOT):
    repo = Path(repo).resolve()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ('runtime.py', 'worker_check.py'):
        raise ValueError('Select the frozen runtime.py or worker_check.py launcher')
    script = repo / args.pop(0)
    expected_launcher = read(repo / 'batch.json')['frozen_files'].get(script.name)
    if not expected_launcher or sha(script) != expected_launcher:
        raise ValueError('Selected launcher differs from frozen source')
    runtime = prepare_runtime(repo)
    activate_runtime(repo, runtime)
    original = sys.argv
    try:
        sys.argv = [str(script), *args]
        runpy.run_path(str(script), run_name='__main__')
    finally:
        sys.argv = original
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
