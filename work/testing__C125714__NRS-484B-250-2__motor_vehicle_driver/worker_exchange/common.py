"""Small, standard-library-only file and identity helpers."""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath

SETS = ('demo-train', 'demo-test', 'held-out', 'full-train', 'full-test')
SKILLS = ('law-grounded-cells', 'law-relevance-mapping', 'law-cell-bindings',
          'law-judgment-observables', 'scenario-coverage-cases', 'carla-scenario-build')


def read(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if Path(tmp).exists():
            Path(tmp).unlink()


def name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('Unsafe identifier: ' + str(value))
    return value


def within(root, relative):
    raw = PurePosixPath(str(relative))
    if raw.is_absolute() or not raw.parts or any(p in ('..', '.') for p in raw.parts) or '\\' in str(relative):
        raise ValueError('Expected a relative contained path: ' + str(relative))
    root = Path(root).resolve()
    path = root.joinpath(*raw.parts)
    # A symlink into the tree is also forbidden: portable packages carry files.
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError('Symlink in package: ' + str(relative))
    if root not in path.resolve().parents:
        raise ValueError('Path escapes root: ' + str(relative))
    return path


def assignment_id(a, role):
    # Demo/full overlap must not create a second implementation.
    return '__'.join(name(str(x)) for x in (role, a['cell_id'], a['law_id'], a['actor']))


def tree(root):
    result = {}
    for path in sorted(Path(root).rglob('*')):
        rel = path.relative_to(root)
        if any(p in ('.git', '__pycache__', '.pytest_cache') for p in rel.parts) or path.suffix == '.pyc':
            continue
        within(root, rel.as_posix())
        if path.is_file():
            result[rel.as_posix()] = sha(path)
    return result
