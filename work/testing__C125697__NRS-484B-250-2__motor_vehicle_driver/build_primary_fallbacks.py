"""Build three distinct, synthetic physical-risk alternatives for the first case."""
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__off_ego_left_near_time'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    primary = json.loads((HERE/'construction.json').read_text())
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    if sha(HERE/entry['construction']) != entry['construction_sha256']:
        raise ValueError('Primary construction changed after proof')
    original = json.loads(next(item['content'] for item in primary['files']
                               if item['path'] == 'config.json'))
    spec = importlib.util.spec_from_file_location('test_runner', HERE/'tests/test_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plans = [
        ('fallback1', 'site.other_approach; site.routes.other[0]',
         'Native other-vehicle spawn/approach check', 'other actor cannot spawn or reach its sourced approach',
         lambda c: (c['site'].__setitem__('other_approach', [15, -14, 0, 90]),
                    c['site']['routes']['other'].__setitem__(0, [15, -14]))),
        ('fallback2', 'site.cameras.approach',
         'original approach source-camera frame coverage',
         'complete approaching body or entrance head absent from original approach frames',
         lambda c: c['site']['cameras'].__setitem__('approach', [6, -8, 14, 35, -35, 0])),
        ('fallback3', 'ego_release_frame',
         'original complete-body entry time versus controller target',
         'ego entry misses the planned same-time engineering target',
         lambda c: c.__setitem__('ego_release_frame', 24)),
    ]
    candidates = []
    for ident, knob, metric, failure, change in plans:
        config = copy.deepcopy(original)
        change(config)
        with tempfile.TemporaryDirectory() as temporary:
            site_dir = Path(temporary)
            module.write_review(site_dir, config)
            site_files = {p.name: p.read_text() for p in site_dir.iterdir() if p.is_file()}
        bundle = copy.deepcopy(primary)
        for item in bundle['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(config, indent=2, allow_nan=False)+'\n'
                item.pop('source', None)
            elif item['path'] in site_files:
                item['content'] = site_files[item['path']]
                item.pop('source', None)
        bundle['status'] = 'synthetic_diagnostic_only'
        path = HERE/(ident+'-construction.json')
        path.write_text(json.dumps(bundle, indent=2, allow_nan=False)+'\n')
        candidates.append({
            'id': ident, 'construction': path.name, 'construction_sha256': sha(path),
            'trigger': {'source': 'retained Native capture and original source-camera streams',
                        'metric': metric, 'failure_condition': failure},
            'changed_knobs': [knob],
        })
    entry['candidate_risk'] = {
        'status': 'physical',
        'reason': 'Native spawn geometry, camera coverage and controller timing at a median crossing can fail independently during physical capture; each fallback changes one engineering cause.'
    }
    entry['candidates'] = candidates
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'case_id': CASE, 'candidate_sha256': {c['id']: c['construction_sha256'] for c in candidates}}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
