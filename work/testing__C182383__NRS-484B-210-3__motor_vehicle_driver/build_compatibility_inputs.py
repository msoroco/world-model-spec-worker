"""Build marked software diagnostics from the pinned saved fixture."""
import hashlib
import json
from pathlib import Path
from analysis import envelope_from_rows
from right_pass_envelope import measure_data
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
        raise ValueError('diagnostic exceeds return size')

def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = json.loads(MANIFEST.read_text())
    base = json.loads(EXAMPLE.read_text())
    mapping = [json.loads(x) for x in base['files']['video_frames.jsonl'].splitlines()]
    trace = [json.loads(x) for x in base['files']['trace.jsonl'].splitlines()]
    for entry, case in zip(manifest['cases'], plan['cases']):
        suffix = case['case_id'].removeprefix(AID + '__')
        fixture = json.loads(json.dumps(base))
        narrow = suffix.startswith('narrow')
        off = case['requested_off_pavement']
        passing = case['requested_right_pass']
        paved_right = 4.0 if narrow else 5.5
        ego_y = [3.0, 5.0] if narrow and off else [4.0, 6.0] if off else [1.2, 3.2]
        rows = []
        frame_rows = []
        for i, (mapped, motion) in enumerate(zip(mapping, trace)):
            s = -8.0 + 2.5 * i if passing else -8.0
            row = {'frame': i, 'native_frame': mapped['carla_frame'], 'original_frame': mapped['carla_frame'],
                   'time_s': mapped['time_s'], 'actor_ids': ['synthetic-ego', 'synthetic-target'],
                   'ego_position_xyz_m': motion['position_m'], 'ego_speed_mps': motion['speed_mps'],
                   'ego_body_s_bounds_m': [s, s + 3.8], 'ego_body_y_bounds_m': ego_y,
                   'target_body_s_bounds_m': [0.0, 3.8], 'target_body_y_bounds_m': [-1.0, 1.0],
                   'paved_y_bounds_m': [-5.0, paved_right]}
            rows.append(row)
            frame_rows.append({**mapped, 'video_frame': i, 'native_frame': mapped['carla_frame']})
        history = {'source_kind': 'synthetic_diagnostic_fixture', 'assignment_id': AID,
                   'case_id': case['case_id'], 'reviewed_site_sha256': 'a' * 64,
                   'map_sha256': 'b' * 64, 'driver_actor_id': 'synthetic-driver',
                   'actor_ids': ['synthetic-ego', 'synthetic-target'],
                   'overtaken_actor_source': 'synthetic-target-pose', 'public_highway': True,
                   'paved_surface_classified': True, 'adjacent_surface_classified': True,
                   'paved_surface_source': 'synthetic-independent-surface-classification',
                   'paved_boundary_source': 'synthetic-surveyed-paved-edge',
                   'connected_route_source': 'synthetic-connected-route',
                   'requested_right_pass': passing, 'samples': rows}
        envelope = envelope_from_rows(history)
        measurement = measure_data(envelope)
        texts = {'right-pass-history.json': json.dumps(history, sort_keys=True) + '\n',
                 'right-pass-envelope.json': json.dumps(envelope, sort_keys=True) + '\n',
                 'right-pass-measurement.json': json.dumps(measurement, sort_keys=True) + '\n',
                 'video_frames.jsonl': ''.join(json.dumps(x, sort_keys=True) + '\n' for x in frame_rows)}
        receipt = {'source_kind': 'synthetic_diagnostic_fixture', 'diagnostic_fixture': True,
                   'case_id': case['case_id'], 'physical_acceptance': False, 'legal_verdict': None}
        for key, name in [('history_sha256', 'right-pass-history.json'),
                          ('envelope_sha256', 'right-pass-envelope.json'),
                          ('measurement_sha256', 'right-pass-measurement.json'),
                          ('frame_map_sha256', 'video_frames.jsonl')]:
            receipt[key] = hashlib.sha256(texts[name].encode()).hexdigest()
        receipt['trace_sha256'] = hashlib.sha256(base['files']['trace.jsonl'].encode()).hexdigest()
        texts['original-source-receipt.json'] = json.dumps(receipt, sort_keys=True) + '\n'
        fixture['files'].update(texts)
        generator = HERE / 'diagnostics' / (suffix + '-generator.json')
        put(generator, fixture, compact=True)
        recipe = HERE / 'diagnostics' / (suffix + '-recipe.json')
        put(recipe, {'format': 'worker-fixture-recipe',
                     'sources': [{'path': 'diagnostic-input.json', 'source': 'runtime/fixtures/example.json', 'sha256': sha(EXAMPLE)}],
                     'generator': {'source': str(generator.relative_to(ROOT)), 'sha256': sha(generator)}})
        keys = ('right_side_pass_event', 'paved_surface_classification', 'physical_necessity_review')
        reqs = [{'disposition_index': d['disposition_index'], 'requirement': d['requirement'],
                 'source': d['source'], 'output_key': keys[d['disposition_index']],
                 'method': 'source_sealed_paved_edge_measurement', 'value_type': 'object', 'kind': 'measured',
                 'inputs': ['right-pass-history.json', 'right-pass-envelope.json', 'original-source-receipt.json', 'trace.jsonl']}
                for d in plan['requirement_dispositions']]
        contract = HERE / 'diagnostics' / (suffix + '-measurement-contract.json')
        put(contract, {'format': 'worker-measurement-contract', 'case_id': case['case_id'],
                       'requirements': reqs,
                       'negative': {'remove': ['right-pass-envelope.json'],
                                    'error_contains': 'Missing required source: right-pass-envelope.json'}})
        entry['fixture_recipe'] = str(recipe.relative_to(ROOT))
        entry['measurement_contract'] = str(contract.relative_to(HERE))
        entry['measurement_procedure'] = {'entrypoint': 'analysis.py',
                                          'method': 'source-sealed original body envelopes and independent paved-edge readback'}
    put(MANIFEST, manifest)
    return len(manifest['cases'])

if __name__ == '__main__':
    print('paved-edge compatibility diagnostics:', build())
