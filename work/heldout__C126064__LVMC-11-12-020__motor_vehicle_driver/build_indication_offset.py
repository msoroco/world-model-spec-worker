"""Build source-shaped exact button-placement sweep members for CPU proof.

Only work under this assignment is written. The canonical selected manifest is
updated separately after each member has its complete proof chain.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
BASE = ASSIGNMENT + '__button_indicated_course'
POINTS = {'0000': 0., '0001': 1., '0002': .5}
SWEEP = ASSIGNMENT + '__c126064_indication_offset'
SOURCES = ('native_runner.py', 'marked_course_native.py',
           'turn_source_recorder.py', 'marked_course_measurement.py',
           'marked_course_finalizer.py')


def write(name, value):
    path = ROOT / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def build(point):
    offset = POINTS[point]
    suffix = 'c126064_indication_offset-' + point
    case = ASSIGNMENT + '__' + suffix
    stem = suffix
    template = json.loads((ROOT / 'button-indicated_course-construction.json').read_text())
    proposal = deepcopy(template)
    proposal['case_id'] = case
    description = proposal['recording_description']
    description['channels'].append({
        'name': 'realized_indication_placement_offset_m', 'unit': 'm',
        'sampling_rate_hz': 20,
        'method': 'source-hashed original indication pose to Native readback',
        'time_window': 'all original turn frames',
        'reference_frame': 'Native world coordinates and sourced unit placement axis',
        'uncertainty': 'physical pixels and municipal authorization need original review'})
    proposal['recording_description'] = description
    for item in proposal['files']:
        name = item['path']
        if name == 'config.json':
            config = json.loads(item['content'])
            config['selected_case_id'] = case
            config['case']['case_id'] = case
            config['case']['recording_description'] = deepcopy(description)
            config['engineering']['indication_offset_m'] = offset
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif name == 'runner.py':
            item['content'] = item['content'].replace(BASE, case)
        elif name in SOURCES:
            item['content'] = (ROOT / name).read_text()
        elif name.startswith('tests/'):
            item['content'] = (ROOT / name).read_text()
    construction = stem + '-construction.json'
    construction_sha = write(construction, proposal)

    fixture = json.loads((ROOT / 'button-indicated-diagnostic.json').read_text())
    files = fixture['files']
    authority = json.loads(files['authority_source_original.json'])
    authority['placement_axis_xy'] = [1., 0.]
    original = json.dumps(authority, sort_keys=True) + '\n'
    scene = json.loads(files['marked_intersection.json'])
    scene['case_id'] = case
    scene['authority_source_sha256'] = sha256(original.encode()).hexdigest()
    scene['physical_indications_xy_m'] = [[offset, 0.]]
    if offset:
        scene.update(source_indications_xy_m=[[0., 0.]],
                     placement_offset_m=offset,
                     realized_placement_offset_m=[offset])
    else:
        for field in ('source_indications_xy_m', 'placement_offset_m',
                      'realized_placement_offset_m'):
            scene.pop(field, None)
    files['authority_source_original.json'] = original
    files['marked_intersection.json'] = json.dumps(scene) + '\n'
    diagnostic = stem + '-diagnostic.json'
    diagnostic_sha = write(diagnostic, fixture)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': f'work/{ASSIGNMENT}/{diagnostic}',
                           'sha256': diagnostic_sha}],
              'generator': {'source': f'work/{ASSIGNMENT}/{diagnostic}',
                            'sha256': diagnostic_sha}}
    recipe_name = stem + '-recipe.json'
    write(recipe_name, recipe)

    contract = json.loads((ROOT / 'button-indicated-measurement-contract.json').read_text())
    contract['case_id'] = case
    write(stem + '-measurement-contract.json', contract)
    return {'case_id': case, 'construction': construction,
            'construction_sha256': construction_sha,
            'diagnostic': diagnostic, 'recipe': recipe_name,
            'measurement_contract': stem + '-measurement-contract.json'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--point', choices=POINTS, required=True)
    print(json.dumps(build(parser.parse_args().point), indent=2))
