"""Exercise signed construction and saved analysis on explicit synthetic sources."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__ordinary_red_signed'


def materialize(target):
    construction = json.loads((ROOT / 'selected-primary/ordinary_red_signed/construction.json').read_text())
    if construction['case_id'] != CASE:
        raise ValueError('Signed construction case differs')
    for item in construction['files']:
        path = target / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    (target / 'construction.json').write_text(json.dumps(construction) + '\n')


def run(target, *args):
    env = __import__('os').environ.copy()
    env['PYTHONPATH'] = str(REPO / 'runtime/pipeline/scenario_pipeline')
    return subprocess.run([sys.executable, str(target / args[0]), *args[1:]],
                          cwd=target, env=env, capture_output=True, text=True)


def sources(target):
    spec = importlib.util.spec_from_file_location('ordinary_proof', ROOT / 'prove-selected-finalizer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.sources(target)
    actors_path = target / 'native-raw-actors.jsonl'
    actors = [json.loads(line) for line in actors_path.read_text().splitlines()]
    for actor in actors:
        actor['blueprint'] = 'vehicle.tesla.model3'
    actors_path.write_text(''.join(json.dumps(actor) + '\n' for actor in actors))
    sys.path.insert(0, str(target))
    try:
        from exception_road import readback
        source = readback((target / 'red-curb-road.xodr').read_text())
    finally:
        sys.path.pop(0)
    map_path = target / 'native-map-readback.json'
    map_row = json.loads(map_path.read_text())
    map_row.update(sign_readback=source['sign_readback'],
                   mailbox_readback=source['mailbox_readback'])
    map_path.write_text(json.dumps(map_row) + '\n')


def prove():
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='C150142-signed-') as tmp:
        parent = Path(tmp)
        positive = parent / 'positive'
        materialize(positive)
        check = run(positive, 'runner.py', '--check')
        if check.returncode:
            raise AssertionError('Signed runner check failed: ' + check.stderr[-1000:])
        sources(positive)
        output = positive / 'analysis-report.json'
        saved = run(positive, 'finalize_selected.py', '--attempt', str(positive),
                    '--output', str(output))
        if saved.returncode:
            raise AssertionError('Signed saved analysis failed: ' + saved.stderr[-1000:])
        report = json.loads(output.read_text())
        observation = report['measurements']['signed_curb_observation']['value']
        if observation['displayed_sign_classes'] != ['no_parking'] or \
           observation['red_curb_stationary_duration_s'] != 5.95 or \
           observation['legal_verdict'] is not None:
            raise AssertionError('Signed observation differs')
        negative = parent / 'missing-sign'
        materialize(negative)
        sources(negative)
        path = negative / 'native-map-readback.json'
        row = json.loads(path.read_text())
        del row['sign_readback']
        path.write_text(json.dumps(row) + '\n')
        rejected = run(negative, 'finalize_selected.py', '--attempt', str(negative),
                       '--output', str(negative / 'analysis-report.json'))
        if rejected.returncode == 0 or 'Missing source-bound signed-curb readback' not in rejected.stderr:
            raise AssertionError('Missing signed source was accepted')
        wrong_vehicle = parent / 'wrong-vehicle'
        materialize(wrong_vehicle)
        sources(wrong_vehicle)
        path = wrong_vehicle / 'native-raw-actors.jsonl'
        actors = [json.loads(line) for line in path.read_text().splitlines()]
        actors[0]['blueprint'] = 'vehicle.unknown'
        path.write_text(''.join(json.dumps(actor) + '\n' for actor in actors))
        rejected_vehicle = run(wrong_vehicle, 'finalize_selected.py',
            '--attempt', str(wrong_vehicle),
            '--output', str(wrong_vehicle / 'analysis-report.json'))
        if rejected_vehicle.returncode == 0 or 'Native vehicle blueprint differs' not in rejected_vehicle.stderr:
            raise AssertionError('Changed Native vehicle identity was accepted')
        negative_road = parent / 'missing-road-sign'
        materialize(negative_road)
        path = negative_road / 'red-curb-road.xodr'
        path.write_text((ROOT / 'native/red-curb-road.xodr').read_text())
        rejected_road = run(negative_road, 'runner.py', '--check')
        if rejected_road.returncode == 0:
            raise AssertionError('Changed authored sign construction was accepted')
    return {'case_id': CASE, 'signed_saved_analysis': 'passed',
            'stationary_duration_s': 5.95,
            'negative_rejections': ['missing-sign-readback', 'changed-native-vehicle',
                                    'changed-authored-road'],
            'source_kind': 'synthetic_native_sample',
            'media_decoded': False, 'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
