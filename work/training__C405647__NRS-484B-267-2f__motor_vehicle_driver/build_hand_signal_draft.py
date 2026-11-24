"""Prepare the distinct hand-signal branch with source-bound diagnostics."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__visible_hand_signal'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    source = HERE / 'current-fixture/controlled_1'
    target = HERE / 'draft-hand-signal/source'
    shutil.copytree(source, target, dirs_exist_ok=True)
    for name in ('driver_hand_track.jsonl', 'hand_signal_review.json'):
        shutil.copyfile(HERE / 'hand-signal-source' / name, target / name)
    hand_review = json.loads((target / 'hand_signal_review.json').read_text())
    hand_review['source_sha256'] = {name: sha(target / name) for name in
        ('video_frames.jsonl', 'vehicle_poses.jsonl', 'driver_hand_track.jsonl')}
    write(target / 'hand_signal_review.json', hand_review)
    context = json.loads((target / 'emergency_context.json').read_text())
    context['case_id'] = CASE
    context['hand_signal_review_source'] = 'synthetic-fixture:driver-hand-frames-80-99'
    write(target / 'emergency_context.json', context)
    spec = json.loads((HERE / 'current-controlled_1-diagnostic.json').read_text())
    write(HERE / 'draft-hand-signal/diagnostic.json', spec)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': path.relative_to(target).as_posix(),
                           'source': path.relative_to(ROOT).as_posix(),
                           'sha256': sha(path)}
                          for path in sorted(target.rglob('*')) if path.is_file()],
              'generator': {'source': (HERE / 'draft-hand-signal/diagnostic.json').relative_to(ROOT).as_posix(),
                            'sha256': sha(HERE / 'draft-hand-signal/diagnostic.json')}}
    write(HERE / 'draft-hand-signal/recipe.json', recipe)
    original = json.loads((HERE / 'current-bundles/controlled_1/primary/construction.json').read_text())
    original['case_id'] = CASE
    original['measurement_plan']['source'] += ', driver_hand_track.jsonl, hand_signal_review.json'
    original['measurement_plan']['visible_preparation_indicator'] = 'source-driver hand pose frames 80-99; original visibility pending'
    original['recording_description']['limitations'].append('Source-driver proxy identity and hand signal need original four-camera sightline review')
    for item in original['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config.update({'case_id': CASE, 'selected_case_id': CASE,
                           'case_suffix': 'visible_hand_signal',
                           'supported_case_ids': [CASE],
                           'requested_hand_signal_side': 'R'})
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'runner.py':
            item['content'] = (HERE / 'native/hand_signal_runner.py').read_text()
        elif item['path'] == 'measure_approach.py':
            item['content'] = (HERE / 'native/measure_hand_signal_approach.py').read_text()
        elif item['path'] == 'finalize.py':
            item['content'] = (HERE / 'native/finalize_hand_signal.py').read_text()
        elif item['path'] == 'tests/test_native.py':
            item['content'] = (HERE / 'native/tests/test_hand_signal_bundle.py').read_text()
    original['files'].append({'path': 'hand_signal_pose.py',
                              'content': (HERE / 'native/hand_signal_pose.py').read_text()})
    original['files'].append({'path': 'measure_hand_signal.py',
                              'content': (HERE / 'native/measure_hand_signal.py').read_text()})
    write(HERE / 'draft-hand-signal/primary/construction.json', original)
    print(json.dumps({'case_id': CASE,
                      'construction_sha256': sha(HERE / 'draft-hand-signal/primary/construction.json'),
                      'recipe_sha256': sha(HERE / 'draft-hand-signal/recipe.json'),
                      'selected': False}))


if __name__ == '__main__':
    main()
