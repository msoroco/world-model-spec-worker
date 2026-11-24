"""Make synthetic case-source fixtures for CPU analyzer tests only."""
import hashlib
import json
from pathlib import Path


def dump(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), sort_keys=True) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(folder):
    repo = folder.parents[1]
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        short = entry['case_id'].rsplit('__', 1)[-1]
        case_dir = folder / 'cases' / short
        config = json.loads(next(f['content'] for f in json.loads((case_dir / 'construction.json').read_text())['files'] if f['path'] == 'config.json'))
        case = config['case']
        source_dir = case_dir / 'diagnostic-sources'
        source_dir.mkdir(exist_ok=True)
        polygon = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
        site = {'cell_id': 'C229439', 'parking_polygon': polygon, 'diagnostic_fixture': True}
        device = {'device_id': 'diagnostic-sign', 'exact_instruction': case['exact_instruction'],
                  'governed_polygon': polygon, 'authority_source': 'synthetic diagnostic only',
                  'placement_source': 'synthetic diagnostic only', 'traffic_purpose_source': 'synthetic diagnostic only',
                  'legal_consistency_source': 'synthetic diagnostic only', 'diagnostic_fixture': True}
        rows = []
        for index in range(900):
            halted = 300 <= index < 500
            rows.append({'frame': index + 1, 'case_id': entry['case_id'], 'subject_id': 'diagnostic-vehicle',
                         'device_id': 'diagnostic-sign', 'device_instruction': case['exact_instruction'],
                         'time_s': round(index / 20, 2), 'device_effective': case['device_mode'] == 'effective',
                         'traffic_conflict': halted and case['exception'] == 'traffic_conflict',
                         'law_direction': halted and case['exception'] == 'law',
                         'police_direction': halted and case['exception'] == 'police_direction',
                         'device_direction': halted and case['exception'] == 'device_direction',
                         'speed_mps': 0 if halted else 1, 'halt_activity': case['halt_action'] if halted else 'travel',
                         'body_corners_xy': [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]],
                         'prohibited_actions': [case['halt_action']]})
        hashes = {}
        for name, value in (('site-source.json', site), ('device-source.json', device), ('actor_rows.json', rows)):
            hashes[name] = dump(source_dir / name, value)
        attempt = {'source_format': 'synthetic_diagnostic', 'diagnostic_fixture': True,
                   'frame_count': 900, 'first_frame': 1, 'case_id': entry['case_id'],
                   'subject_id': 'diagnostic-vehicle', 'device_id': 'diagnostic-sign',
                   'device_instruction': case['exact_instruction'], 'parking_polygon': polygon,
                   'halt_action': case['halt_action'],
                   'source_context': {name: {'path': name, 'sha256': digest} for name, digest in hashes.items()}}
        hashes['attempt.json'] = dump(source_dir / 'attempt.json', attempt)
        recipe_path = case_dir / 'fixture-recipe.json'
        recipe = json.loads(recipe_path.read_text())
        previous = [source for source in recipe['sources'] if source['path'] not in hashes]
        recipe['sources'] = [{'path': name, 'source': (source_dir / name).relative_to(repo).as_posix(), 'sha256': digest}
                             for name, digest in sorted(hashes.items())] + previous
        dump(recipe_path, recipe)
    dump(manifest_path, manifest)


if __name__ == '__main__':
    build(Path(__file__).resolve().parent)
