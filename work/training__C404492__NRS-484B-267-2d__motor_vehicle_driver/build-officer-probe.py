"""Bind an unselected source-shaped officer diagnostic to current runtime."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
CASE = AID + '__officer_directed'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), sort_keys=True) + '\n')


def main():
    source = HERE / 'current-fixture' / 'controlled_2' / 'emergency_context.json'
    context = json.loads(source.read_text())
    context['case_id'] = CASE
    context['officer_directed_otherwise'] = True
    context['officer_instruction_sources'] = {
        key: 'synthetic-fixture:' + key for key in (
            'officer_instruction_source', 'officer_identity_source',
            'officer_instruction_text', 'officer_instruction_recipient',
            'officer_instruction_timing_source', 'officer_instruction_reviewer')}
    target = HERE / 'current-fixture' / 'officer_directed' / 'emergency_context.json'
    write(target, context)
    recipe = json.loads((HERE / 'current-controlled_2-recipe.json').read_text())
    for entry in recipe['sources']:
        if entry['path'] == 'emergency_context.json':
            entry['source'] = target.relative_to(REPO).as_posix()
            entry['sha256'] = sha(target)
    recipe_path = HERE / 'current-officer_directed-recipe.json'
    write(recipe_path, recipe)
    draft = json.loads((HERE / 'draft-officer-manifest.json').read_text())['cases'][0]
    probe = json.loads((HERE / 'current-preparing-probe-manifest.json').read_text())
    entry = {key: draft[key] for key in (
        'case_id', 'construction', 'construction_sha256', 'measurement_contract',
        'measurement_procedure', 'candidate_risk', 'candidates')}
    entry.update(id='primary', kind='delivery',
                 fixture_recipe=recipe_path.relative_to(REPO).as_posix())
    probe['cases'] = [entry]
    output = HERE / 'current-officer-probe-manifest.json'
    write(output, probe)
    print(json.dumps({'context_sha256': sha(target),
                      'recipe_sha256': sha(recipe_path),
                      'probe_sha256': sha(output)}))


if __name__ == '__main__':
    main()
