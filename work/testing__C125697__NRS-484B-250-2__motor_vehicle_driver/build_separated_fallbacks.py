"""Build three distinct physical-risk retries for separated entry."""
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'cases/off_ego_left_separated'
CASE = HERE.name + '__off_ego_left_separated'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    if entry.get('candidates'):
        raise ValueError('Separated fallbacks already built; retain bound proofs')
    primary = json.loads((HERE / entry['construction']).read_text())
    original = json.loads(next(item['content'] for item in primary['files']
                               if item['path'] == 'config.json'))
    spec = importlib.util.spec_from_file_location('test_runner', HERE / 'tests/test_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plans = [
        ('fallback1', ['site.ego_approach', 'site.routes.ego[0]'],
         'retained Native ego spawn and approach waypoint',
         'ego spawn or approach cannot reach the selected crossing',
         lambda cfg: (cfg['site'].__setitem__('ego_approach', [-4, 0, 0, 0]),
                      cfg['site']['routes']['ego'].__setitem__(0, [-4, 0]))),
        ('fallback2', ['site.cameras.approach'],
         'original approach camera complete-body and signal-head coverage',
         'approach stream lacks a complete body or governing head in original frames',
         lambda cfg: cfg['site']['cameras'].__setitem__('approach', [2, -3, 11, 20, -35, 0])),
        ('fallback3', ['other_release_frame'],
         'original complete-body separation versus controller target',
         'measured entry gap compresses relative to the planned separated-entry target',
         lambda cfg: cfg.__setitem__('other_release_frame', 64)),
    ]
    candidates = []
    for ident, knobs, metric, failure, mutate in plans:
        cfg = copy.deepcopy(original)
        mutate(cfg)
        with tempfile.TemporaryDirectory() as temporary:
            site_dir = Path(temporary)
            module.write_review(site_dir, cfg)
            packet = {path.name: path.read_text() for path in site_dir.iterdir() if path.is_file()}
        bundle = copy.deepcopy(primary)
        for item in bundle['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(cfg, indent=2, allow_nan=False) + '\n'
                item.pop('source', None)
            elif item['path'] in packet:
                item['content'] = packet[item['path']]
                item.pop('source', None)
        path = OUT / (ident + '-construction.json')
        path.write_text(json.dumps(bundle, indent=2, allow_nan=False) + '\n')
        candidates.append({
            'id': ident, 'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'retained Native capture and original source-camera streams',
                        'metric': metric, 'failure_condition': failure},
            'changed_knobs': knobs,
        })
    entry['candidate_risk'] = {
        'status': 'physical',
        'reason': 'Spawn/route geometry, original camera coverage and relative entry timing can independently fail; each fallback changes one engineering cause.'
    }
    entry['candidates'] = candidates
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'case_id': CASE, 'candidates': {c['id']: c['construction_sha256'] for c in candidates}}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
