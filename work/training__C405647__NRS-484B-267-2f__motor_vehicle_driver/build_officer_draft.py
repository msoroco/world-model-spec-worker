"""Prepare the distinct officer branch with source-bound diagnostics."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__officer_direction'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    source = HERE / 'current-fixture/controlled_2'
    target = HERE / 'draft-officer/source'
    shutil.copytree(source, target, dirs_exist_ok=True)
    for name in ('officer_track.jsonl', 'officer_direction.json'):
        shutil.copyfile(HERE / 'officer-source' / name, target / name)
    officer_review = json.loads((target / 'officer_direction.json').read_text())
    officer_review['source_sha256'] = {name: sha(target / name) for name in
        ('video_frames.jsonl', 'vehicle_poses.jsonl', 'officer_track.jsonl')}
    write(target / 'officer_direction.json', officer_review)
    context = json.loads((target / 'emergency_context.json').read_text())
    context['case_id'] = CASE
    context['officer_directed_otherwise'] = True
    context['officer_direction_review_source'] = 'synthetic-fixture:officer-direction-frames-100-200'
    write(target / 'emergency_context.json', context)
    spec = json.loads((HERE / 'current-controlled_2-diagnostic.json').read_text())
    write(HERE / 'draft-officer/diagnostic.json', spec)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': path.relative_to(target).as_posix(),
                           'source': path.relative_to(ROOT).as_posix(),
                           'sha256': sha(path)}
                          for path in sorted(target.rglob('*')) if path.is_file()],
              'generator': {'source': (HERE / 'draft-officer/diagnostic.json').relative_to(ROOT).as_posix(),
                            'sha256': sha(HERE / 'draft-officer/diagnostic.json')}}
    write(HERE / 'draft-officer/recipe.json', recipe)
    original = json.loads((HERE / 'current-bundles/controlled_2/primary/construction.json').read_text())
    original['case_id'] = CASE
    original['measurement_plan']['source'] += ', officer_track.jsonl, officer_direction.json'
    original['measurement_plan']['officer_direction_exception'] = 'officer direction pose frames 100-200; original identity and visibility pending'
    original['recording_description']['limitations'].append('Law-enforcement identity and officer direction need original four-camera review')
    for item in original['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config.update({'case_id': CASE, 'selected_case_id': CASE,
                           'case_suffix': 'officer_direction',
                           'supported_case_ids': [CASE],
                           'requested_officer_direction_side': 'R'})
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'runner.py':
            item['content'] = (HERE / 'native/officer_direction_runner.py').read_text()
        elif item['path'] == 'measure_approach.py':
            item['content'] = (HERE / 'native/measure_officer_approach.py').read_text()
        elif item['path'] == 'finalize.py':
            item['content'] = (HERE / 'native/finalize_officer.py').read_text()
        elif item['path'] == 'tests/test_native.py':
            item['content'] = (HERE / 'native/tests/test_officer_bundle.py').read_text()
    original['files'].append({'path': 'hand_signal_pose.py',
                              'content': (HERE / 'native/hand_signal_pose.py').read_text()})
    original['files'].append({'path': 'measure_officer.py',
                              'content': (HERE / 'native/measure_officer.py').read_text()})
    write(HERE / 'draft-officer/primary/construction.json', original)
    print(json.dumps({'case_id': CASE,
                      'construction_sha256': sha(HERE / 'draft-officer/primary/construction.json'),
                      'recipe_sha256': sha(HERE / 'draft-officer/recipe.json'),
                      'selected': False}))


if __name__ == '__main__':
    main()
