"""Build four-camera synthetic source recipe for the exact signed red curb."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__ordinary_red_signed'


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def replace_rows(text, update):
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    for row in rows:
        update(row)
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                   for row in rows)


def build(candidate='primary'):
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown signed candidate')
    construction_path = (ROOT / 'selected-primary/ordinary_red_signed/construction.json'
                         if candidate == 'primary' else
                         ROOT / 'selected-fallbacks/ordinary_red_signed' / candidate /
                         'construction.json')
    construction = json.loads(construction_path.read_text())
    bundle = {item['path']: item['content'] for item in construction['files']}
    cfg = json.loads(bundle['config.json'])
    if construction['case_id'] != CASE or cfg['road_sha256'] != sha(bundle['red-curb-road.xodr']):
        raise ValueError('Signed diagnostic construction changed')
    original = json.loads((ROOT / 'selected-diagnostics/reference' /
                           (candidate + '.json')).read_text())
    files = original['files']
    files['road.xodr'] = bundle['red-curb-road.xodr']
    files['native-raw-actors.jsonl'] = replace_rows(
        files['native-raw-actors.jsonl'],
        lambda row: row.update(blueprint='vehicle.tesla.model3'))
    map_row = json.loads(files['native-map-readback.json'])
    map_row.update(road_sha256=cfg['road_sha256'],
                   sign_readback={'present': True,
                                  'displayed_classes': ['no_parking'],
                                  'center_x_m': 40},
                   mailbox_readback={'present': False,
                                     'center_x_m': 40,
                                     'center_y_m': -7.4})
    files['native-map-readback.json'] = encode(map_row)
    capture = json.loads(files['capture/manifest.json'])
    capture['sources']['road.xodr'] = cfg['road_sha256']
    files['capture/manifest.json'] = encode(capture)
    report = json.loads(files['native-capture-report.json'])
    report.update(case_id=CASE, candidate_id=candidate,
                  config_sha256=sha(bundle['config.json']))
    files['native-capture-report.json'] = encode(report)
    path = ROOT / 'selected-diagnostics/ordinary_red_signed' / (candidate + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode(original))
    rel = path.relative_to(REPO).as_posix()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-source.json',
                           'source': rel, 'sha256': sha(path.read_text())}],
              'generator': {'source': rel, 'sha256': sha(path.read_text())}}
    recipe_path = path.with_name(candidate + '-recipe.json')
    recipe_path.write_text(encode(recipe))
    if candidate != 'primary':
        manifest = json.loads((ROOT / 'execution-manifest-diagnostic-ordinary_red_signed.json').read_text())
        manifest['cases'][0]['fixture_recipe'] = recipe_path.relative_to(REPO).as_posix()
        manifest_path = ROOT / ('execution-manifest-diagnostic-ordinary_red_signed-' +
                                candidate + '.json')
        manifest_path.write_text(encode(manifest))
    return {'case_id': CASE, 'spec_sha256': sha(path.read_text()),
            'recipe_sha256': sha(recipe_path.read_text()),
            'source_camera_count': len(original['videos'])}


if __name__ == '__main__':
    print(encode(build(sys.argv[1] if len(sys.argv) > 1 else 'primary')), end='')
