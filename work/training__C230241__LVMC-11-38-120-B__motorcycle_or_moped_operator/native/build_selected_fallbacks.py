"""Bind risk-based spawn alternatives to the unchanged two-case capture plan."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    manifest_path = PACKAGE / 'selected-probe-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        primary = json.loads((PACKAGE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in primary['files']
                                 if item['path'] == 'config.json'))
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Motorcycle and vendor spawn pair, mutual clearance, and lamp field of view need original Native pilot verification before the 600-frame capture.',
        }
        entry['candidates'] = []
        for ident, ego, vendor, metric in (
                ('fallback1', 1, 2, 'spawn_pair_clearance_m'),
                ('fallback2', 2, 3, 'alternate_spawn_road_alignment_m'),
                ('fallback3', 0, 3, 'vendor_occlusion_fraction')):
            folder = PACKAGE / 'selected/fallbacks' / case / ident
            folder.mkdir(parents=True, exist_ok=True)
            alternative = json.loads(json.dumps(primary))
            variant = json.loads(json.dumps(config))
            variant['candidate_id'] = ident
            variant['spawn_point_index'] = ego
            variant['vendor_spawn_point_index'] = vendor
            for item in alternative['files']:
                if item['path'] == 'config.json':
                    item['content'] = json.dumps(variant, indent=2) + '\n'
            write(folder / 'config.json', variant)
            write(folder / 'construction.json', alternative)
            entry['candidates'].append({
                'id': ident,
                'construction': str((folder / 'construction.json').relative_to(PACKAGE)),
                'construction_sha256': sha(folder / 'construction.json'),
                'trigger': {
                    'metric': metric,
                    'source': 'original Native pilot spawn and four-camera evidence',
                    'failure_condition': 'primary spawn clearance, alignment, or unobstructed lamp view is inadequate in calibrated original Native review',
                },
                'changed_knobs': ['spawn_point_index', 'vendor_spawn_point_index'],
                'fixture_recipe': entry['fixture_recipe'],
            })
    write(manifest_path, manifest)
    return {'cases': len(manifest['cases']),
            'fallbacks': sum(len(entry['candidates']) for entry in manifest['cases']),
            'manifest_sha256': sha(manifest_path)}


if __name__ == '__main__':
    print(json.dumps(build()))
