"""Build source-bound synthetic pedestrian candidates for current CPU proof."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def build(response):
    selected = ROOT / ('selected-pedestrian-' + response)
    base = ROOT / ('rider-30s-primary/source' if response == 'clear' else
                   'selected-rider-bicycle-conflict/source')
    source = selected / 'source'
    shutil.copytree(base, source, dirs_exist_ok=True)
    rider = read_rows(source / 'rider_native_samples.jsonl')
    draft = read_rows(ROOT / f'draft-pedestrian-cases/{response}/primary/source-rows.jsonl')
    assert len(rider) == 600 and len(draft) == 480
    pedestrian = []
    for index, ego in enumerate(rider):
        row = dict(draft[min(index, 479)])
        row['native_frame'] = ego['native_frame']
        row['time_s'] = ego['time_s']
        row['ego_body_xy'] = ego['ego_body_xy']
        pedestrian.append(row)
    write_rows(source / 'pedestrian_native_samples.jsonl', pedestrian)
    policy = json.loads((ROOT / f'draft-pedestrian-cases/{response}/primary/construction.json').read_text())
    policy['capture_frames'] = 600
    write(source / 'pedestrian_geometry.json', policy)
    write(source / 'pedestrian-source-manifest.json', {
        'source_kind': 'synthetic_cpu_fixture', 'accepted': False,
        'samples_sha256': sha(source / 'pedestrian_native_samples.jsonl'),
        'geometry_sha256': sha(source / 'pedestrian_geometry.json'),
        'pedestrian_type': 'pedestrian',
        'pedestrian_blueprint': 'walker.pedestrian.0001',
        'pedestrian_actor_id': 109})
    (selected / 'diagnostic-spec.json').write_bytes((base.parent / 'diagnostic-spec.json').read_bytes())
    sources = [{'path': str(path.relative_to(source)),
                'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
               for path in sorted(source.rglob('*')) if path.is_file()]
    write(selected / 'fixture-recipe.json', {
        'format': 'worker-fixture-recipe',
        'generator': {'source': str((selected / 'diagnostic-spec.json').relative_to(REPO)),
                      'sha256': sha(selected / 'diagnostic-spec.json')},
        'sources': sources})
    spec = importlib.util.spec_from_file_location('rider_30s_builder', ROOT / 'build-rider-30s-primary.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    digests = {}
    for candidate in ('primary', 'fallback1', 'fallback2'):
        draft_path = ROOT / f'draft-pedestrian-exact-cases/pedestrian_{response}/{candidate}/construction.json'
        target = selected / candidate / 'construction.json'
        module.convert(draft_path, target)
        construction = json.loads(target.read_text())
        construction['static_checks'] = [
            'exact pedestrian case and declared walker source class',
            '600 synchronized synthetic Native-shaped frames at 20 Hz',
            'four source camera views with pedestrian pixels unverified',
            'source-bound synthetic pedestrian and ego body samples']
        for item in construction['files']:
            name = item['path']
            content = item['content']
            if name == 'runner.py':
                content = content.replace("config['duration_s']!=24", "config['duration_s']!=30")
                content = content.replace('frames!=480', 'frames!=600')
                content = content.replace('frames==480', 'frames==600')
                content = content.replace("'expected_frames':480", "'expected_frames':600")
            elif name == 'finalize.py':
                content = content.replace('count != 480', 'count != 600').replace('480-frame', '600-frame')
            elif name == 'pedestrian_engineering.py':
                content = (ROOT / 'native/pedestrian_engineering.py').read_text()
                content = content.replace('FRAMES = 480', 'FRAMES = 600')
                content = content.replace('Expected 480 saved rows', 'Expected 600 saved rows')
                content = content.replace("row['native_frame'] != 1000+i or row['time_s'] != round(i/20, 2)",
                                          "row['native_frame'] != 100+i or row['time_s'] != round((i+1)/20, 2)")
            elif name == 'finalize_pedestrian.py':
                content = (ROOT / 'native/finalize_pedestrian.py').read_text()
                rider_finalizer = (ROOT / 'native/finalize_rider.py').read_text()
                derive = rider_finalizer[rider_finalizer.index('def derive_channels('):rider_finalizer.index('def finalize(')]
                a = derive.index("            elif name == 'ru.pedestrian':")
                b = derive.index("            elif name.startswith('ru.')", a)
                derive = derive[:a] + ("            elif name == 'ru.pedestrian':\n"
                    "                value = {'native_actor_id': 109, 'native_body_xy_m': rider['pedestrian_body_xy'],\n"
                    "                         'source_frame': rider['native_frame'], 'synthetic_diagnostic': True}\n") + derive[b:]
                content = content.replace('def measured_original(', derive + 'def measured_original(')
                content = content.replace("    source=json.loads(source_path.read_text())",
                    "    if not source_path.is_file():\n        raise ValueError('Missing required source: pedestrian-source-manifest.json')\n    source=json.loads(source_path.read_text())")
                content = content.replace('    recording=[]\n',
                    '    derive_channels(attempt, description, motion, pedestrian_rows, mapping)\n    recording=[]\n')
                content = content.replace('!=480', '!=600').replace('480-frame', '600-frame')
                content = content.replace('verify_original_joins(attempt,480)', 'verify_original_joins(attempt,600)')
                content = content.replace("'capture_frames':480", "'capture_frames':600")
                content = content.replace('entire 24 s', 'entire 30 s').replace('[0,24]', '[0,30]')
                content = content.replace("'measurements':measured,'original_joins':original,",
                    "'measurements':{'pedestrian_conflict_observation':{'method':'finalize',"
                    "'value':measured,'sources':{'pedestrian_native_samples.jsonl':sha(attempt/'pedestrian_native_samples.jsonl'),"
                    "'pedestrian_geometry.json':sha(attempt/'pedestrian_geometry.json'),"
                    "'pedestrian-source-manifest.json':sha(source_path)}}},'original_joins':original,")
            if name.endswith('.py'):
                ast.parse(content, filename=name)
            item['content'] = content
        write(target, construction)
        digests[candidate] = sha(target)
    print(json.dumps({'response': response, 'frames': 600, 'constructions': digests,
                      'fixture_recipe_sha256': sha(selected / 'fixture-recipe.json')}))


if __name__ == '__main__':
    for response in ('clear', 'conflict'):
        build(response)
