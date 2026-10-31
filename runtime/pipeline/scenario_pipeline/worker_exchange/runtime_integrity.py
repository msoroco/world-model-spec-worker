"""Fail closed on incomplete portable runtime exports and worker skills."""
import ast
import sys
from pathlib import Path

from .common import read, sha, within


REQUIRED_MODULES = (
    'catalog.py', 'delivery_definitions.py', 'demo_rule_evidence.py',
    'intentions.py', 'lean_work.py', 'migrate_law_split.py',
    'organize_sets.py', 'organize_work.py', 'pipeline.py',
    'production_verdicts.py', 'recording_readmes.py',
    'recover_core_evidence.py', 'run_selected.py',
    'production_metadata.py', 'trace_derivations.py', 'trace_json.py',
)
EXTERNAL_IMPORTS = frozenset((
    'PIL', 'agents', 'carla', 'matplotlib', 'networkx', 'numpy',
    'scipy', 'shapely', 'tqdm',
))


def verify(repo, runtime, batch):
    repo, runtime = Path(repo).resolve(), Path(runtime).resolve()
    if runtime != repo / 'runtime/pipeline':
        raise ValueError('Unexpected portable runtime location')
    manifest_path = runtime / 'SOURCE-MANIFEST.json'
    if sha(manifest_path) != batch['runtime']['source_manifest_sha256']:
        raise ValueError('Frozen runtime manifest changed')
    manifest = read(manifest_path)
    files = manifest['files']
    if set(manifest.get('required_local_modules', ())) != set(REQUIRED_MODULES):
        raise ValueError('Incomplete declared portable module closure')
    for name in REQUIRED_MODULES:
        relative = 'scenario_pipeline/' + name
        if relative not in files:
            raise ValueError('Missing required local module from source manifest: ' + relative)
    for relative, digest in files.items():
        path = within(runtime, relative)
        if not path.is_file() or sha(path) != digest:
            raise ValueError('Missing or changed frozen runtime file: ' + relative)

    pipeline = runtime / 'scenario_pipeline'
    if (pipeline / 'skills').exists():
        raise ValueError('Duplicate worker skill location inside runtime')
    from batch_pipeline.stages import SKILLS, SKILLS_ROOT
    if SKILLS_ROOT.resolve() != (repo / 'skills').resolve():
        raise ValueError('Stage loader does not use the worker skill directory')
    for name in sorted(set(SKILLS.values()) | {'law-grounded-cells', 'worker-preparation'}):
        relative = 'skills/' + name + '/SKILL.md'
        path = within(repo, relative)
        if not path.is_file() or sha(path) != batch['frozen_files'].get(relative):
            raise ValueError('Missing or changed frozen worker skill: ' + relative)

    local = {p.stem for p in pipeline.glob('*.py')}
    local |= {p.name for p in pipeline.iterdir() if p.is_dir()}
    helpers = runtime / 'python'
    local |= {p.stem for p in helpers.glob('*.py')}
    local |= {p.name for p in helpers.iterdir() if p.is_dir()}
    local.add('scenario_pipeline')
    for relative in files:
        if not relative.endswith('.py') or not relative.startswith(('scenario_pipeline/', 'python/', 'tests/')):
            continue
        path = within(runtime, relative)
        tree = ast.parse(path.read_text(), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name.split('.')[0] for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split('.')[0]]
            else:
                continue
            for name in names:
                if name not in local and name not in sys.stdlib_module_names and name not in EXTERNAL_IMPORTS:
                    raise ValueError('Unresolved portable Python import: ' + relative + ' -> ' + name)
    return {'runtime_files_verified': len(files),
            'required_local_modules_verified': len(REQUIRED_MODULES),
            'worker_skills_verified': len(set(SKILLS.values()) | {'law-grounded-cells', 'worker-preparation'}),
            'import_closure_verified': True}
