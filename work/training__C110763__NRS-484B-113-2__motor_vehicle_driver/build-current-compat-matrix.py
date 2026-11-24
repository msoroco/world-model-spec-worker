"""Bind both draft cases and candidates to current source-only fixture recipes."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    fixture_log = HERE / 'current-b-fixture-only.log'
    fixture = Path(json.loads(fixture_log.read_text().splitlines()[-1])['fixture'])
    if ROOT / '.runtime-work' not in fixture.parents:
        raise ValueError('Fixture must remain in ignored runtime work')
    example = json.loads((HERE / 'current-600-primary-generator.json').read_text())
    b = {'files': {}, 'graphs': example['graphs'], 'videos': example['videos']}
    for relative in example['files']:
        b['files'][relative] = (fixture / relative).read_text()
    generator = HERE / 'current-600-controlled-generator.json'
    generator.write_text(json.dumps(b, separators=(',', ':')) + '\n')
    assignment = ROOT / 'inputs' / HERE.name / 'assignment.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input-assignment.json',
                           'source': str(assignment.relative_to(ROOT)), 'sha256': sha(assignment)}],
              'generator': {'source': str(generator.relative_to(ROOT)), 'sha256': sha(generator)}}
    recipe_path = HERE / 'current-600-controlled-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'current_runtime_eight_draft_compatibility_probe'
    for entry in manifest['cases']:
        entry['fixture_recipe'] = str((HERE / ('current-600-primary-recipe.json' if entry['case_id'].endswith('probe_1')
                                              else 'current-600-controlled-recipe.json')).relative_to(ROOT))
    path = HERE / 'current-compat-matrix-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'generator_sha256': sha(generator), 'recipe_sha256': sha(recipe_path),
                      'manifest_sha256': sha(path), 'case_count': len(manifest['cases'])}, sort_keys=True))


if __name__ == '__main__':
    main()
