"""Stage corrected Native physical criteria without invalidating accepted drafts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = {
    'primary': 'yield_ego_left_near_time',
    'right': 'yield_ego_right_near_time',
    'separated': 'yield_ego_left_separated',
    'opposite': 'yield_opposite_left_turn',
}


def serialize(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def staged(prefix, suffix, candidate=None):
    folder = ROOT / 'cases' / suffix
    source_name = (candidate + '-construction.json') if candidate else 'construction.json'
    construction = json.loads((folder / source_name).read_text())
    files = construction['files']
    site = json.loads(next(row['content'] for row in files if row['path'] == 'site.json'))
    config_row = next(row for row in files if row['path'] == 'config.json')
    config = json.loads(config_row['content'])
    config['physical_completion'] = {
        'criterion': 'intersection_clearance',
        'motion_source': 'crossing_history.jsonl',
        'body_key': 'ego.body_vertices_xy_m',
        'intersection_polygon_xy_m': site['crossing_polygon_xy_m'],
        'exit_axis': 0, 'exit_sign': 1,
        'context_sources': ['site.json'],
    }
    config_row['content'] = serialize(config)
    staged_name = ((candidate + '-') if candidate else '') + 'physical-construction.json'
    path = folder / staged_name
    path.write_text(serialize(construction))
    manifest = json.loads((ROOT / (prefix + '-candidate-manifest.json')).read_text())
    entry = manifest['cases'][0]
    entry['construction'] = str(path.relative_to(ROOT))
    entry['construction_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    for key in ('offline', 'compatibility', 'negative', 'saved_processing',
                'candidate_risk', 'candidates', 'physical_preparation'):
        entry.pop(key, None)
    manifest['status'] = 'staged_physical_completion_diagnostic'
    manifest_name = ('physical-candidate-manifest.json' if prefix == 'primary' and not candidate
                     else f'physical-{prefix}-{candidate}-manifest.json' if candidate
                     else f'physical-{prefix}-manifest.json')
    (ROOT / manifest_name).write_text(serialize(manifest))
    return {'prefix': prefix, 'candidate': candidate or 'primary',
            'construction_sha256': entry['construction_sha256'],
            'manifest': manifest_name}


def main():
    for prefix, suffix in CASES.items():
        print(json.dumps(staged(prefix, suffix), sort_keys=True))
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            print(json.dumps(staged(prefix, suffix, candidate), sort_keys=True))


if __name__ == '__main__':
    main()
