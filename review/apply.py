"""Apply a reviewed runtime refresh after the active worker has stopped.

Run from a clean checkout of the delivery branch after cherry-picking this
review commit. This script changes no scope, case list, or accepted evidence.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'review'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def inventory(root):
    return {str(path.relative_to(root)): sha(path) for path in sorted(root.rglob('*'))
            if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts
            and path.suffix != '.pyc' and path.name != 'SOURCE-MANIFEST.json'}


def main():
    config = json.loads((REVIEW / 'config.json').read_text())
    batch_path = ROOT / 'batch.json'
    batch = json.loads(batch_path.read_text())
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    if branch != batch['return_branch'] or batch['batch_id'] != config['batch_id']:
        raise SystemExit('Apply only on the stopped delivery branch for this batch')
    subprocess.run([sys.executable, str(REVIEW / 'quarantine-stale-generated.py')],
                   cwd=ROOT, check=True)
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise SystemExit('Commit reviewed changes and worker checkpoints before cutover')
    current = ROOT / batch['runtime']['root']
    if sha(current / 'SOURCE-MANIFEST.json') != batch['runtime']['source_manifest_sha256']:
        raise SystemExit('Delivery branch runtime differs from its frozen baseline')
    candidate = REVIEW / 'runtime'
    manifest = json.loads((candidate / 'SOURCE-MANIFEST.json').read_text())
    if inventory(candidate) != manifest['files']:
        raise SystemExit('Staged runtime files differ from the source-hashed snapshot')
    next_dir = ROOT / '.runtime-work' / 'replacement-runtime'
    if next_dir.exists():
        raise SystemExit('Prior incomplete replacement exists; inspect it')
    shutil.copytree(candidate, next_dir, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for retained in ('docs', 'skills', 'stage_contracts.json'):
        source = current / retained
        target = next_dir / retained
        if target.exists():
            raise SystemExit('Snapshot unexpectedly shadows retained ' + retained)
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.is_file():
            shutil.copy2(source, target)
        else:
            raise SystemExit('Missing retained runtime material: ' + retained)
    write(next_dir / 'SOURCE-MANIFEST.json', {
        'source': 'reviewed current scenario_pipeline snapshot',
        'files': inventory(next_dir),
        'policy': 'One current JSON graph runtime; no pickle-only compatibility path',
    })
    old_manifest = batch['runtime']['source_manifest_sha256']
    old_dir = ROOT / '.runtime-work' / 'replaced-runtime'
    if old_dir.exists():
        raise SystemExit('Prior replaced runtime exists; inspect it')
    current.rename(old_dir)
    next_dir.rename(current)
    shutil.rmtree(old_dir)  # No old-code archive.
    for name in ('AGENT_PROMPT.md', 'README.md', 'START_HERE.md'):
        shutil.copy2(REVIEW / name, ROOT / name)
    shutil.copy2(REVIEW / 'run-worker.sh', ROOT / 'scripts/run-worker.sh')
    shutil.copy2(REVIEW / 'quarantine-stale-generated.py', ROOT / 'scripts/quarantine-stale-generated.py')
    runtime_hash = sha(current / 'SOURCE-MANIFEST.json')
    batch['runtime']['source_manifest_sha256'] = runtime_hash
    judgment_paths = {}
    for source in sorted((REVIEW / 'judgment').glob('*.json')) if (REVIEW / 'judgment').exists() else []:
        target = ROOT / 'inputs' / 'judgment_ranges' / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        judgment_paths[source.stem] = 'inputs/judgment_ranges/' + source.name
    for aid in batch['assignments']:
        folder = ROOT / 'work' / aid
        assignment_path = ROOT / 'inputs' / aid / 'assignment.json'
        assignment = json.loads(assignment_path.read_text())
        matching = [sid for sid in assignment['set_ids'] if sid in judgment_paths]
        if matching:
            if len(matching) != 1:
                raise SystemExit('Ambiguous testing judgment reference: ' + aid)
            assignment['judgment_range_reference'] = judgment_paths[matching[0]]
            write(assignment_path, assignment)
            batch['assignments'][aid]['input_sha256'] = sha(assignment_path)
        path = folder / 'execution-manifest.json'
        if path.is_file():
            value = json.loads(path.read_text())
            if value.get('runtime_manifest_sha256') == old_manifest:
                value['runtime_manifest_sha256'] = runtime_hash
                write(path, value)
        result_path = folder / 'result.json'
        if result_path.is_file():
            result = json.loads(result_path.read_text())
            result['input_sha256'] = batch['assignments'][aid]['input_sha256']
            if result.get('status') == 'ready':
                result['status'] = 'partial'
                result['readiness_kind'] = 'implementation_checkpoint'
                result['reason'] = ((result.get('reason') or '') + ' Runtime refresh requires new exact-case and saved proofs.').strip()
            write(result_path, result)
    frozen = batch['frozen_files']
    prefix = batch['runtime']['root'] + '/'
    for key in [key for key in frozen if key.startswith(prefix)]:
        del frozen[key]
    for key, value in inventory(current).items():
        frozen[prefix + key] = value
    frozen[prefix + 'SOURCE-MANIFEST.json'] = runtime_hash
    for name in ('AGENT_PROMPT.md', 'README.md', 'START_HERE.md',
                 'scripts/run-worker.sh', 'scripts/quarantine-stale-generated.py'):
        frozen[name] = sha(ROOT / name)
    for sid, relative in judgment_paths.items():
        frozen[relative] = sha(ROOT / relative)
    for aid in batch['assignments']:
        relative = 'inputs/' + aid + '/assignment.json'
        frozen[relative] = sha(ROOT / relative)
    write(batch_path, batch)
    print(json.dumps({'batch': batch['batch_id'], 'runtime_manifest_sha256': runtime_hash,
                      'assigned': len(batch['assignments']), 'old_code_preserved': False}, indent=2))


if __name__ == '__main__':
    main()
