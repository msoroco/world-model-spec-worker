"""Worker-side validation. Never imports returned code, SQLite, or CARLA."""
import ast
import sys
from pathlib import Path
from .common import digest, read, sha, tree, within

TERMINAL = ('prepared', 'partial', 'blocked')
FORBIDDEN_SUFFIXES = {'.sqlite', '.db', '.mkv', '.mp4', '.webm', '.zip', '.egg', '.so', '.pyc'}


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
    repo = Path(repo)
    batch = read(repo / 'batch.json')
    if batch.get('mode') == 'six_step_preparation':
        from .preparation import check as preparation_check
        return preparation_check(repo, complete=complete)
    expected = batch['frozen_files']
    if batch.get('format') != 'worker-batch-v1' or not 1 <= batch['max_workers'] <= 4:
        raise ValueError('Invalid worker batch')
    actual = tree(repo)
    for rel, checksum in expected.items():
        if actual.get(rel) != checksum:
            raise ValueError('Frozen input changed/missing: ' + rel)
    for rel in actual:
        if rel in expected or rel == 'batch.json':
            continue
        parts = Path(rel).parts
        if len(parts) < 3 or parts[0] != 'work' or parts[1] not in batch['assignments']:
            raise ValueError('Unapproved package file: ' + rel)
        inspect_file(within(repo, rel))
    results = {}
    for aid in batch['assignments']:
        result_path = repo / 'work' / aid / 'result.json'
        if not result_path.exists():
            if complete:
                raise ValueError('Missing result: ' + aid)
            continue
        if not (repo / 'work' / aid / 'HANDOFF.md').is_file():
            raise ValueError('Missing assignment handoff: ' + aid)
        value = read(result_path)
        if value.get('assignment_id') != aid or value.get('status') not in TERMINAL:
            raise ValueError('Invalid result identity/status: ' + aid)
        if value.get('input_sha256') != sha(repo / 'inputs' / aid / 'assignment.json'):
            raise ValueError('Result binds stale inputs: ' + aid)
        if not isinstance(value.get('remaining_gpu_checks'), list) or not isinstance(value.get('tests'), list):
            raise ValueError('Missing test/uncertainty report: ' + aid)
        if value['status'] in ('blocked', 'partial') and not value.get('reason'):
            raise ValueError('Partial/blocked result needs a reason')
        if value['status'] == 'prepared':
            if not value['tests'] or not value['remaining_gpu_checks']:
                raise ValueError('Prepared work needs CPU test evidence and explicit GPU checks')
            for test in value['tests']:
                if not test.get('command') or test.get('exit_code') != 0:
                    raise ValueError('Prepared work has missing/failing tests')
                log = within(repo / 'work' / aid, test['log'])
                if not log.is_file() or sha(log) != test['sha256']:
                    raise ValueError('Missing/changed test log')
        # No test command or proposed code is executed by this validator.
        validate_imports(repo, aid)
        results[aid] = value
    return {'batch_id': batch['batch_id'], 'results': results,
            'package_sha256': digest(actual), 'files': actual,
            'verification': 'Static validation only; worker test claims are not independent acceptance'}


def validate_imports(repo, aid):
    """Catch ordinary undeclared imports. Dynamic imports remain a declared limitation."""
    source = Path(repo) / 'work' / aid
    inputs = read(Path(repo) / 'inputs' / aid / 'assignment.json')
    allowed = set(sys.stdlib_module_names) | set(inputs.get('external_imports', [])) | {'worker_exchange'}
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
