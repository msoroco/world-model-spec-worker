"""Source-shaped synthetic fixtures for compatibility only, never original evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = REPO / 'runtime/fixtures/example.json'
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('diagnostic exceeds return limit')


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    base = json.loads(BASE.read_text())
    for case, entry in zip(plan['cases'], manifest['cases']):
        suffix = case['case_id'].removeprefix(AID + '__')
        fixture = json.loads(json.dumps(base))
        context = {'case_id': case['case_id'], 'map_sha256': 'a' * 64,
                   'lane_design': case['lane_design_request'], 'intersection_type': case['intersection_request'],
                   'independent_route_intent': case['route_request'],
                   'approach_lane_ids': ['-1', '-2'], 'right_turn_lane_id': '-1',
                   'intersection_entry_station_m': 10, 'intersection_exit_station_m': 20}
        for name in ('public_highway', 'roadway_boundary', 'lane_design', 'exclusive_turn_control',
                     'intersection_type', 'intersection_boundary', 'straight_route', 'right_turn_route',
                     'sightline_obstruction', 'driver_identity', 'motor_vehicle', 'independent_route_intent'):
            context[name + '_source'] = 'synthetic-' + name
        rows = []
        for i in range(9):
            station = i * 4
            if case['route_request'] == 'stop_before': station = min(station, 6)
            lane = '-2' if case['ego_lane_request'] == 'adjacent_through' or (case['ego_lane_request'] == 'right_then_adjacent' and i >= 2) else '-1'
            rows.append({'frame': i, 'time_s': i / 20, 'lane_id': lane, 'ego_station_m': station,
                         'speed_mps': 0 if case['route_request'] == 'stop_before' and i >= 2 else 8,
                         'connected_route': 'none' if case['route_request'] == 'stop_before' else case['route_request']})
        context_text = json.dumps(context, sort_keys=True) + '\n'
        trace_text = ''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows)
        receipt = {'assignment_id': AID, 'case_id': case['case_id'],
                   'source_kind': 'synthetic_diagnostic_fixture', 'diagnostic_fixture': True,
                   'fps': 20, 'frame_count': 9,
                   'context_sha256': hashlib.sha256(context_text.encode()).hexdigest(),
                   'trace_sha256': hashlib.sha256(trace_text.encode()).hexdigest(),
                   'physical_acceptance': False, 'legal_verdict': None}
        fixture['files']['context.json'] = context_text
        fixture['files']['original-trace.jsonl'] = trace_text
        fixture['files']['receipt.json'] = json.dumps(receipt, sort_keys=True) + '\n'
        generator = HERE / 'diagnostics' / (suffix + '-generator.json')
        put(generator, fixture)
        recipe = HERE / 'diagnostics' / (suffix + '-recipe.json')
        put(recipe, {'format': 'worker-fixture-recipe',
                     'sources': [{'path': 'diagnostic-input.json', 'source': 'runtime/fixtures/example.json', 'sha256': sha(BASE)}],
                     'generator': {'source': str(generator.relative_to(REPO)), 'sha256': sha(generator)}})
        keys = ('public_highway_and_lane_design', 'right_turn_lane_occupancy', 'intersection_traversal')
        contract = HERE / 'diagnostics' / (suffix + '-measurement-contract.json')
        put(contract, {'format': 'worker-measurement-contract', 'case_id': case['case_id'],
                       'requirements': [{'disposition_index': d['disposition_index'], 'requirement': d['requirement'],
                                         'source': d['source'], 'output_key': keys[d['disposition_index']],
                                         'method': 'source_sealed_turn_lane_measurement', 'value_type': 'object',
                                         'kind': 'measured', 'inputs': ['context.json', 'original-trace.jsonl', 'receipt.json']}
                                        for d in plan['requirement_dispositions']],
                       'negative': {'remove': ['context.json'], 'error_contains': 'Missing required source: context.json'}})
        entry['fixture_recipe'] = str(recipe.relative_to(REPO))
        entry['measurement_contract'] = str(contract.relative_to(HERE))
        entry['measurement_procedure'] = {'entrypoint': 'analysis.py', 'method': 'source-sealed original lane and intersection measurement'}
        entry['acquisition'] = {name: {'entrypoint': 'runner.py', 'evidence': 'original Native source and four-camera frame map',
                                       'method': 'source-hashed original Native capture'}
                                for name in ('public_highway_and_lane_design', 'exclusive_right_turn_control',
                                             'intersection_entry_and_exit', 'independent_route_intent',
                                             'original_lane_and_vehicle_motion', 'sightline_and_four_camera_pixels')}
    put(HERE / 'execution-manifest.json', manifest)
    return len(manifest['cases'])


if __name__ == '__main__':
    print('diagnostic recipes:', build())
