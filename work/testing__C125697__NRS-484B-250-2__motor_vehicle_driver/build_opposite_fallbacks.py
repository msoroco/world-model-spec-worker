"""Add three distinct physical-risk candidates to the isolated opposite case."""
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'cases/off_opposite_left_turn'
CASE = HERE.name + '__off_opposite_left_turn'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    path = HERE / 'opposite-candidate-manifest.json'
    manifest = json.loads(path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    if entry['candidates']:
        raise ValueError('Opposite fallbacks already built; retain bound proofs')
    primary = json.loads((HERE / entry['construction']).read_text())
    config = json.loads(next(row['content'] for row in primary['files']
                             if row['path'] == 'config.json'))
    spec = importlib.util.spec_from_file_location('test_runner', HERE / 'tests/test_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plans = [
        ('fallback1', ['site.other_approach', 'site.routes.other[0]'],
         'opposite-lane spawn and westbound approach reachability',
         'other vehicle cannot spawn or travel from the east approach',
         lambda cfg: (cfg['site'].__setitem__('other_approach', [34, 1.75, 0, 180]),
                      cfg['site']['routes']['other'].__setitem__(0, [34, 1.75]))),
        ('fallback2', ['site.cameras.approach'],
         'original approach-camera view of opposing body and signal head',
         'approach camera loses the westbound body or governing head',
         lambda cfg: cfg['site']['cameras'].__setitem__('approach', [2, 5, 11, -20, -35, 0])),
        ('fallback3', ['other_release_frame'],
         'source-measured opposite-vehicle entry and turn timing',
         'opposing vehicle entry or left-turn timing drifts from target',
         lambda cfg: cfg.__setitem__('other_release_frame', 24)),
    ]
    for ident, knobs, metric, failure, mutate in plans:
        cfg = copy.deepcopy(config)
        mutate(cfg)
        with tempfile.TemporaryDirectory() as temp:
            module.write_review(Path(temp), cfg)
            packet = {item.name: item.read_text() for item in Path(temp).iterdir()}
        bundle = copy.deepcopy(primary)
        for item in bundle['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(cfg, indent=2, allow_nan=False) + '\n'
                item.pop('source', None)
            elif item['path'] in packet:
                item['content'] = packet[item['path']]
                item.pop('source', None)
        construction = OUT / (ident + '-construction.json')
        construction.write_text(json.dumps(bundle, indent=2, allow_nan=False) + '\n')
        entry['candidates'].append({
            'id': ident,
            'construction': str(construction.relative_to(HERE)),
            'construction_sha256': sha(construction),
            'trigger': {'source': 'retained Native motion and original source-camera streams',
                        'metric': metric, 'failure_condition': failure},
            'changed_knobs': knobs,
        })
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {item['id']: item['construction_sha256'] for item in entry['candidates']}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
