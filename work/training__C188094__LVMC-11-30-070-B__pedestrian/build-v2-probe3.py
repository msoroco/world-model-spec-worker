"""Construct an exact unmarked-intersection case in the same frozen cell."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__probe_3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Exact source replacement lost: ' + old[:80])
    return source.replace(old, new)


def main():
    base = json.loads((HERE / 'draft-exact/probe_1/primary/construction.json').read_text())
    construction = json.loads(json.dumps(base))
    construction['case_id'] = CASE
    files = construction['files']
    for file in files:
        if file['path'] == 'config.json':
            config = json.loads(file['content'])
            config['case_id'] = CASE
            config['selected_case_id'] = CASE
            config['case']['case_id'] = CASE
            config['supported_case_ids'].append(CASE)
            config['crossing_case'] = 'unmarked'
            file['content'] = json.dumps(config, indent=2) + '\n'
        elif file['path'] == 'path.py':
            file['content'] = replace_once(file['content'], '"outside": 12.0}',
                                           '"outside": 12.0, "unmarked": 21.0}')
        elif file['path'] == 'runner.py':
            runner = file['content']
            runner = replace_once(runner, 'from geometry import check as geometry_check, open_drive',
                                  'from unmarked_geometry import check as geometry_check, open_drive')
            runner = replace_once(runner, "'probe_2': 'outside'}", "'probe_2': 'outside', 'probe_3': 'unmarked'}")
            runner = replace_once(runner, "        (output / 'crossing-context.json').write_text(json.dumps({",
                """        sidewalk_samples = []
        for wp in world.get_map().generate_waypoints(0.5):
            location = wp.transform.location
            if (wp.road_id == 3 and wp.lane_type == carla.LaneType.Sidewalk
                    and abs(location.x - 21) <= 4 and abs(location.y) <= 8):
                sidewalk_samples.append({'road_id': wp.road_id, 'lane_id': wp.lane_id,
                                         'x_m': location.x, 'y_m': location.y})
        if not any(p['y_m'] < -4 for p in sidewalk_samples) or not any(p['y_m'] > 4 for p in sidewalk_samples):
            raise RuntimeError('Original intersecting sidewalk readback incomplete')
        (output / 'sidewalk-edges.json').write_text(json.dumps({
            'source_kind': 'native_map_readback_sidewalk_edges',
            'native_map_sha256': hashlib.sha256((output / 'road.xodr').read_bytes()).hexdigest(),
            'samples': sidewalk_samples}, indent=2) + '\\n')
        (output / 'crossing-context.json').write_text(json.dumps({""")
            runner = replace_once(runner,
                "'crosswalks': [{'kind': 'marked', 'bounds_m': geometry_check()['crosswalk_bounds_m']}],\n            'intersection_inventory': [],",
                """'crosswalks': [{'kind': 'marked', 'bounds_m': geometry_check()['crosswalk_bounds_m']},
                           {'id': 'unmarked-7', 'kind': 'unmarked',
                            'bounds_m': geometry_check()['unmarked_crosswalk_bounds_m']}],
            'intersection_inventory': [{'unmarked_crosswalk_id': 'unmarked-7',
                 'native_junction_id': geometry_check()['unmarked_junction_id'],
                 'incoming_road_id': 1, 'connecting_road_id': 3,
                 'sidewalk_edge_source_path': 'sidewalk-edges.json',
                 'sidewalk_edge_source_sha256': hashlib.sha256(
                     (output / 'sidewalk-edges.json').read_bytes()).hexdigest()}],""")
            file['content'] = runner
        elif file['path'] == 'finalize.py':
            finalizer = file['content']
            finalizer = replace_once(finalizer, 'from measure_crossing import measure',
                                     'from measure_crossing import measure\nfrom unmarked_source_gate import validate as validate_unmarked_source')
            finalizer = replace_once(finalizer,
                                     "('actor-poses.jsonl', 'crossing-context.json', 'road.xodr')",
                                     "('actor-poses.jsonl', 'crossing-context.json', 'road.xodr', 'sidewalk-edges.json')")
            finalizer = replace_once(finalizer, "    joins = verify_original_joins(attempt, 600)",
                """    if config['crossing_case'] == 'unmarked':
        context = json.loads(required(attempt, 'crossing-context.json').read_text())
        validate_unmarked_source(context, required(attempt, 'road.xodr').read_bytes(),
            {'sidewalk-edges.json': required(attempt, 'sidewalk-edges.json').read_bytes()})
    joins = verify_original_joins(attempt, 600)""")
            file['content'] = finalizer
    files.extend({'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('unmarked_geometry.py', 'unmarked_source_gate.py'))
    construction['mechanisms'] = ['authored intersecting street and sidewalk lanes at x=21',
                                  'same pedestrian route timing, camera policy and 20 Hz interval',
                                  'original Native junction and sidewalk readback required']
    construction['status'] = 'partial_unmarked_intersection_native_unverified'
    path = HERE / 'draft-exact/probe_3/primary/construction.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(construction, indent=2) + '\n')
    manifest = json.loads((HERE / 'v2-selected-pair-manifest.json').read_text())
    contract = json.loads((HERE / 'v2-probe1-measurement-contract.json').read_text())
    contract['case_id'] = CASE
    contract['requirements'][0]['inputs'].append('sidewalk-edges.json')
    contract['negative'] = {'remove': ['sidewalk-edges.json'],
                            'error_contains': 'Missing required source: sidewalk-edges.json'}
    (HERE / 'v2-probe3-measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    entry = dict(manifest['cases'][0])
    entry.update(case_id=CASE, construction=str(path.relative_to(HERE)),
                 construction_sha256=sha(path), candidates=[],
                 measurement_contract='v2-probe3-measurement-contract.json',
                 fixture_recipe='work/' + HERE.name + '/v2-probe3-fixture-recipe.json')
    manifest['cases'].append(entry)
    manifest['status'] = 'partial_unmarked_branch_cpu'
    (HERE / 'v2-three-case-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'construction_sha256': sha(path),
                      'manifest_sha256': sha(HERE / 'v2-three-case-manifest.json')}))


if __name__ == '__main__':
    main()
