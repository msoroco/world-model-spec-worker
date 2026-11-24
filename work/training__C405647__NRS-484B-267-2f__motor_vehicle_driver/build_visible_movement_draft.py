"""Prepare a distinct vehicle-movement branch without selecting unproved delivery."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__visible_movement'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    source = HERE / 'current-fixture/controlled_1'
    target = HERE / 'draft-visible/source'
    shutil.copytree(source, target, dirs_exist_ok=True)
    poses = [json.loads(line) for line in (target / 'vehicle_poses.jsonl').read_text().splitlines()]
    for index, pose in enumerate(poses):
        emergency = pose['emergency']
        shift = min(max(index - 79, 0), 20) * .5 / 20
        emergency['x_m'] = round(emergency['x_m'] - shift, 5)
        if 80 <= index < 100:
            emergency['velocity_x_mps'] = -.5
            emergency['speed_mps'] = .5
    (target / 'vehicle_poses.jsonl').write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in poses))
    context = json.loads((target / 'emergency_context.json').read_text())
    context['case_id'] = CASE
    context['preparation_movement_review_source'] = 'synthetic-fixture:vehicle-motion-frames-80-99'
    context['native_source_hashes']['vehicle_poses.jsonl'] = sha(target / 'vehicle_poses.jsonl')
    write(target / 'emergency_context.json', context)
    spec = json.loads((HERE / 'current-controlled_1-diagnostic.json').read_text())
    for index, graph in enumerate(spec['graphs']):
        node = next(node for node in graph['nodes'] if node['id'] == 'emergency')
        shift = min(max(index - 79, 0), 20) * .5 / 20
        node['attributes']['vertex'][0] = round(node['attributes']['vertex'][0] - shift, 5)
        for vertex in node['attributes']['threedbbox']:
            vertex[0] = round(vertex[0] - shift, 5)
    write(HERE / 'draft-visible/diagnostic.json', spec)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': path.relative_to(target).as_posix(),
                           'source': path.relative_to(ROOT).as_posix(),
                           'sha256': sha(path)}
                          for path in sorted(target.rglob('*')) if path.is_file()],
              'generator': {'source': (HERE / 'draft-visible/diagnostic.json').relative_to(ROOT).as_posix(),
                            'sha256': sha(HERE / 'draft-visible/diagnostic.json')}}
    write(HERE / 'draft-visible/recipe.json', recipe)
    original = json.loads((HERE / 'current-bundles/controlled_1/primary/construction.json').read_text())
    original['case_id'] = CASE
    original['measurement_plan']['visible_preparation_indicator'] = 'source vehicle movement frames 80-99; original driver visibility pending'
    original['recording_description']['limitations'].append('Visible vehicle movement needs original four-camera driver sightline review')
    for item in original['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config.update({'case_id': CASE, 'selected_case_id': CASE, 'case_suffix': 'visible_movement',
                           'supported_case_ids': [CASE], 'requested_preparation_movement_mps': .5})
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'runner.py':
            item['content'] = (HERE / 'native/visible_movement_runner.py').read_text()
        elif item['path'] == 'measure_approach.py':
            item['content'] = (HERE / 'native/measure_visible_movement.py').read_text()
        elif item['path'] == 'finalize.py':
            item['content'] = (HERE / 'native/finalize_visible_movement.py').read_text()
        elif item['path'] == 'tests/test_native.py':
            item['content'] = (HERE / 'native/tests/test_visible_bundle.py').read_text()
    write(HERE / 'draft-visible/primary/construction.json', original)
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(HERE / 'draft-visible/primary/construction.json'),
                      'recipe_sha256': sha(HERE / 'draft-visible/recipe.json'), 'selected': False}))


if __name__ == '__main__':
    main()
