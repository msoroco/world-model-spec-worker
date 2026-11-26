"""Build marked rider diagnostics from the pinned saved fixture."""
import hashlib
import json
from pathlib import Path
from abreast import CASES, SOURCES
from analysis import diagnostic_measure
from package_spec import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXAMPLE = ROOT / 'runtime/fixtures/example.json'
MANIFEST = HERE / 'execution-manifest.selected-draft.json'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def put(path, data, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, **({'separators': (',', ':')} if compact else {'indent': 2})) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('rider diagnostic exceeds return size')

def scene_for(case):
    ids = ['ego', 'control'] + (['companion'] if case.riders == 3 else [])
    scene = {'cell_id': 'C233933', 'actor': 'cycle_or_scooter_operator',
             'highway': True, 'sidewalk_absent': True, 'exclusive': case.exclusive,
             'roadway': case.roadway, 'rider_ids': ids, 'ego_id': 'ego',
             'control_id': 'control', 'vehicle_type': 'human_powered_bicycle',
             'moped': False, 'roadway_rect_m': [0., 0., 60., 10.],
             'shoulder_rect_m': [0., 9., 60., 10.],
             'occupied_surface_rect_m': [0., 0., 60., 8.],
             'rider_routes_xy': [[[0., 1. + i], [60., 1. + i]] for i in range(case.riders)]}
    scene.update({name + '_source_sha256': hashlib.sha256(('diagnostic-' + name).encode()).hexdigest() for name in SOURCES})
    return scene

def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = json.loads(MANIFEST.read_text())
    base = json.loads(EXAMPLE.read_text())
    mapping = [json.loads(x) for x in base['files']['video_frames.jsonl'].splitlines()]
    trace = [json.loads(x) for x in base['files']['trace.jsonl'].splitlines()]
    for entry, case_plan in zip(manifest['cases'], plan['cases']):
        case_id = case_plan['case_id']
        suffix = case_id.removeprefix(AID + '__')
        case = next(item for item in CASES if item.name == suffix)
        scene = scene_for(case)
        fixture = json.loads(json.dumps(base))
        rows, frame_rows = [], []
        for i, (mapped, motion) in enumerate(zip(mapping, trace)):
            row = {'frame': i, 'native_frame': mapped['carla_frame'],
                   'original_frame': mapped['carla_frame'], 'time_s': mapped['time_s'],
                   'rider_ids': scene['rider_ids'],
                   'native_actor_ids': ['synthetic-' + rider for rider in scene['rider_ids']],
                   'exclusive': case.exclusive, 'roadway': case.roadway,
                   'rider_xy': [[i / 20, 1. + rider] for rider in range(case.riders)],
                   'rider_speed_mps': [1.0] * case.riders,
                   'ego_position_xyz_m': motion['position_m'],
                   'ego_heading_deg': motion['heading_deg'],
                   'ego_speed_mps': motion['speed_mps']}
            row.update({name + '_source_sha256': scene[name + '_source_sha256'] for name in SOURCES})
            rows.append(row)
            frame_rows.append({**mapped, 'video_frame': i, 'native_frame': mapped['carla_frame']})
        measurement = diagnostic_measure(rows, scene, case)
        history = {'source_kind': 'synthetic_diagnostic_fixture', 'assignment_id': AID,
                   'case_id': case_id, 'reviewed_site_sha256': 'a' * 64,
                   'map_sha256': 'b' * 64, 'scene': scene,
                   'rider_ids': scene['rider_ids'],
                   'native_actor_ids': rows[0]['native_actor_ids'], 'samples': rows}
        texts = {'rider-history.json': json.dumps(history, sort_keys=True) + '\n',
                 'rider-measurement.json': json.dumps(measurement, sort_keys=True) + '\n',
                 'video_frames.jsonl': ''.join(json.dumps(x, sort_keys=True) + '\n' for x in frame_rows)}
        receipt = {'source_kind': 'synthetic_diagnostic_fixture',
                   'diagnostic_fixture': True, 'case_id': case_id,
                   'physical_acceptance': False, 'legal_verdict': None,
                   'history_sha256': hashlib.sha256(texts['rider-history.json'].encode()).hexdigest(),
                   'measurement_sha256': hashlib.sha256(texts['rider-measurement.json'].encode()).hexdigest(),
                   'frame_map_sha256': hashlib.sha256(texts['video_frames.jsonl'].encode()).hexdigest(),
                   'trace_sha256': hashlib.sha256(base['files']['trace.jsonl'].encode()).hexdigest()}
        texts['original-source-receipt.json'] = json.dumps(receipt, sort_keys=True) + '\n'
        fixture['files'].update(texts)
        generator = HERE / 'diagnostics' / (suffix + '-generator.json')
        put(generator, fixture, compact=True)
        recipe = HERE / 'diagnostics' / (suffix + '-recipe.json')
        put(recipe, {'format': 'worker-fixture-recipe',
                     'sources': [{'path': 'diagnostic-input.json', 'source': 'runtime/fixtures/example.json', 'sha256': sha(EXAMPLE)}],
                     'generator': {'source': str(generator.relative_to(ROOT)), 'sha256': sha(generator)}})
        keys = ('bicycle_classification', 'rider_formation', 'exclusive_use_designation')
        reqs = [{'disposition_index': d['disposition_index'], 'requirement': d['requirement'],
                 'source': d['source'], 'output_key': keys[d['disposition_index']],
                 'method': 'source_sealed_rider_measurement', 'value_type': 'object', 'kind': 'measured',
                 'inputs': ['rider-history.json', 'rider-measurement.json', 'original-source-receipt.json', 'trace.jsonl']}
                for d in plan['requirement_dispositions']]
        contract = HERE / 'diagnostics' / (suffix + '-measurement-contract.json')
        put(contract, {'format': 'worker-measurement-contract', 'case_id': case_id,
                       'requirements': reqs,
                       'negative': {'remove': ['rider-history.json'],
                                    'error_contains': 'Missing required source: rider-history.json'}})
        entry['fixture_recipe'] = str(recipe.relative_to(ROOT))
        entry['measurement_contract'] = str(contract.relative_to(HERE))
        entry['measurement_procedure'] = {'entrypoint': 'analysis.py',
                                          'method': 'source-sealed rider identities, formation and exclusive-use designation'}
    put(MANIFEST, manifest)
    return len(manifest['cases'])

if __name__ == '__main__':
    print('rider formation compatibility diagnostics:', build())
