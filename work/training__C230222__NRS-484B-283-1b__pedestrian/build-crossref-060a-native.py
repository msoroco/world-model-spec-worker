"""Prepare two same-cell Native constructions for the marked crossing exception."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.name
LABELS = ('marked', 'outside')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_one(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected Native source shape: ' + old)
    return text.replace(old, new)


def main():
    template = json.loads((HERE / 'v2-primary/probe_1/construction.json').read_text())
    road = (HERE / 'native/road-crosswalk.xodr').read_text()
    cases = []
    for label in LABELS:
        case = BASE + '__crossref_lvmc_11_30_060_a_' + label
        y = 0 if label == 'marked' else 4
        construction = copy.deepcopy(template)
        construction['case_id'] = case
        construction['status'] = 'unselected_crossref_native_cpu_construction'
        for item in construction['files']:
            path, content = item['path'], item['content']
            if path == 'road.xodr':
                content = road
            elif path == 'geometry.py':
                content = replace_one(content,
                    "or road.findall('objects/object'):",
                    "or len(road.findall('objects/object')) != 1 or road.find('objects/object').get('type') != 'crosswalk':")
            elif path == 'engineering.py':
                content = replace_one(content,
                    "if suffix not in ('probe_1', 'probe_2') or ident not in IDS:",
                    "if suffix not in ('crossref_lvmc_11_30_060_a_marked', 'crossref_lvmc_11_30_060_a_outside') or ident != 'primary':")
                content = replace_one(content,
                    "start = .5 if suffix == 'probe_1' else 3.5",
                    "start = .5")
                content = replace_one(content,
                    "'pedestrian_departure_s': start, 'pedestrian_target_speed_mps': 3.0,",
                    "'pedestrian_departure_s': start, 'pedestrian_spawn_y_m': (0 if suffix.endswith('_marked') else 4), 'pedestrian_target_speed_mps': 3.0,")
            elif path == 'runner.py':
                content = replace_one(content,
                    "carla.Location(x=e['pedestrian_spawn_x_m'], y=0, z=.5)",
                    "carla.Location(x=e['pedestrian_spawn_x_m'], y=e['pedestrian_spawn_y_m'], z=.5)")
                content = replace_one(content,
                    "if plan['engineering']['pedestrian_departure_s'] not in (.5, 3.5):",
                    "if plan['engineering']['pedestrian_departure_s'] != .5:")
                content = replace_one(content,
                    "'curb_edge_xy_m': [-3.5, 0]",
                    "'curb_edge_xy_m': [-3.5, e['pedestrian_spawn_y_m']]")
                content = replace_one(content,
                    "'vehicle_conflict_y_m': 0,",
                    "'vehicle_conflict_y_m': e['pedestrian_spawn_y_m'],")
            elif path == 'curb.py':
                content = replace_one(content,
                    "context.get('vehicle_conflict_y_m') != 0:",
                    "context.get('vehicle_conflict_y_m') not in (0, 4):")
            elif path == 'finalize.py':
                content = replace_one(content,
                    "expected = 'conditional_yield_possible' if config['case_suffix'] == 'probe_1' else 'conditional_yield_impossible'",
                    "expected = 'conditional_yield_possible'")
            elif path == 'tests/test_offline.py':
                content = replace_one(content,
                    ".5 if config['case_suffix'] == 'probe_1' else 3.5)",
                    ".5)")
                # The common fallback trigger unit test targets the two selected
                # conditional cases; this crossref pair has no fallback policy.
                start = content.index('    def test_fallback_trigger_boundaries(self):')
                end = content.find('\n    def ', start + 1)
                content = content[:start] + (content[end:] if end >= 0 else '')
            elif path == 'config.json':
                config = json.loads(content)
                config['case_id'] = case
                config['selected_case_id'] = case
                config['case_suffix'] = case.split('__')[-1]
                config['case']['case_id'] = case
                config['supported_case_ids'] = [BASE + '__crossref_lvmc_11_30_060_a_' + one for one in LABELS]
                content = json.dumps(config, indent=2) + '\n'
            item['content'] = content
        out = HERE / 'crossref-060a-native' / label
        out.mkdir(parents=True, exist_ok=True)
        path = out / 'construction.json'
        path.write_text(json.dumps(construction, indent=2) + '\n')
        cases.append({'case_id': case, 'construction': str(path.relative_to(HERE)),
                      'construction_sha256': sha(path), 'crossing_y_m': y,
                      'source_road_sha256': hashlib.sha256(road.encode()).hexdigest(),
                      'status': 'unselected_cpu_construction'})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': BASE,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'unselected_crossref_native_cpu_construction', 'cases': cases}
    (HERE / 'crossref-060a-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'road_sha256': cases[0]['source_road_sha256']}))


if __name__ == '__main__':
    main()
