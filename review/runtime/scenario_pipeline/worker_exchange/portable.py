"""Worker-side validation. Never imports returned code, SQLite, or CARLA."""
import ast
import sys
from pathlib import Path
from .common import digest, read, sha, tree, within

FORBIDDEN_SUFFIXES = {'.sqlite', '.db', '.mkv', '.mp4', '.webm', '.zip', '.egg', '.so', '.pyc'}
RUNTIME_IMPORTS = {'scenario_pipeline', 'numpy', 'networkx', 'shapely', 'PIL', 'yaml',
                   'tqdm', 'matplotlib', 'pydot', 'carla_sgg'}


def inspect_file(path):
    if path.suffix.lower() in FORBIDDEN_SUFFIXES or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Large/binary evidence is not a worker input: ' + str(path))
    text = path.read_text()  # Binary/invalid UTF-8 must fail, not get silently copied.
    if path.name.startswith('.env') or 'PRIVATE KEY-----' in text:
        raise ValueError('Credential-like file is not portable: ' + str(path))
    if path.suffix in ('.py', '.sh'):
        if any(prefix in text for prefix in ('/pscratch/', '/global/homes/', '/global/u1/')):
            raise ValueError('Nonportable filesystem dependency: ' + str(path))
        if path.suffix == '.py':
            ast.parse(text, filename=str(path))
    return text


def check(repo, *, complete=False):
    """Use the current preparation contract; plans-only returns are retired."""
    from .preparation import check as preparation_check
    return preparation_check(repo, complete=complete)


def validate_imports(repo, aid):
    """Catch ordinary undeclared imports. Dynamic imports remain a declared limitation."""
    source = Path(repo) / 'work' / aid
    inputs = read(Path(repo) / 'inputs' / aid / 'assignment.json')
    # These modules are pinned by the portable runtime itself. Assignment
    # declarations cover imports beyond that fixed dependency set.
    allowed = (set(sys.stdlib_module_names) | RUNTIME_IMPORTS |
               set(inputs.get('external_imports', [])) | {'worker_exchange'})
    batch = read(Path(repo) / 'batch.json')
    if batch.get('runtime'):
        from .preparation import runtime_for
        runtime = runtime_for(repo, batch)
        manifest = runtime / 'SOURCE-MANIFEST.json'
        if manifest.is_file():
            for relative in read(manifest)['files']:
                parts = Path(relative).parts
                if len(parts) >= 2 and parts[0] in ('scenario_pipeline', 'python'):
                    allowed.add(Path(parts[1]).stem)
    python = list(source.rglob('*.py'))
    allowed |= {p.stem for p in python} | {p.parent.name for p in python}
    for path in python:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [v.name.split('.')[0] for v in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [node.module.split('.')[0]] if node.module else []
            else:
                continue
            missing = set(names) - allowed
            if missing:
                raise ValueError('Undeclared import in ' + str(path) + ': ' + ', '.join(sorted(missing)))
