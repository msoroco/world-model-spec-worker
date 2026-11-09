"""Materialize explicitly inventoried, hash-bound case diagnostic sources."""
import shutil
from pathlib import Path
from .common import digest, read, sha, tree, within
from .fixture_generator import FORBIDDEN, inspect as inspect_generated, generate

OUTPUTS = FORBIDDEN


def inspect(repo, recipe_path):
    repo = Path(repo).resolve()
    recipe_path = Path(recipe_path).resolve()
    if repo not in recipe_path.parents:
        raise ValueError('Fixture recipe must be in worker repository')
    recipe = read(recipe_path)
    if recipe.get('format') != 'worker-fixture-recipe':
        raise ValueError('Unknown fixture recipe')
    if any(key in recipe for key in ('base', 'remove', 'additions')):
        raise ValueError('Fixture recipe must explicitly inventory sources')
    items = recipe.get('sources')
    if not isinstance(items, list) or not items:
        raise ValueError('Case fixture needs explicit source files')
    sources = {}
    for item in items:
        target, source = item.get('path'), item.get('source')
        if not isinstance(target, str) or not isinstance(source, str) or target in sources:
            raise ValueError('Invalid or duplicate fixture source')
        within(repo, target)  # Validate the destination before creating anything.
        if Path(target).parts[0] in OUTPUTS:
            raise ValueError('Fixture cannot supply package configuration or outputs')
        if Path(source).parts[0] not in ('work', 'runtime', 'inputs'):
            raise ValueError('Fixture source must belong to worker inputs, work, or runtime')
        src = within(repo, source)
        if not src.is_file() or sha(src) != item.get('sha256'):
            raise ValueError('Fixture source missing/changed: ' + source)
        sources[target] = src
    generator = recipe.get('generator')
    if generator is not None:
        source = generator.get('source', '')
        if Path(source).parts[:1] not in (('work',), ('runtime',), ('inputs',)):
            raise ValueError('Diagnostic specification must belong to worker sources')
        path = within(repo, source)
        if not path.is_file() or sha(path) != generator.get('sha256'):
            raise ValueError('Diagnostic specification missing/changed')
        generated = inspect_generated(read(path))
        if set(generated) & set(sources):
            raise ValueError('Diagnostic output shadows an explicit source')
    return recipe, sources


def materialize(repo, recipe_path, output):
    recipe, sources = inspect(repo, recipe_path)
    expected = {item['path']: item['sha256'] for item in recipe['sources']}
    output = Path(output)
    if output.exists():
        raise ValueError('Use a fresh fixture directory')
    output.mkdir(parents=True)
    for relative, source in sources.items():
        target = within(output, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha(target) != expected[relative] or sha(source) != expected[relative]:
            raise ValueError('Fixture source changed during materialization')
    if recipe.get('generator') is not None:
        spec = within(repo, recipe['generator']['source'])
        generate(read(spec), output)
        if sha(spec) != recipe['generator']['sha256']:
            raise ValueError('Diagnostic specification changed during generation')
    return {'recipe_sha256': sha(recipe_path), 'fixture_sha256': digest(tree(output)),
            'output': str(output)}
