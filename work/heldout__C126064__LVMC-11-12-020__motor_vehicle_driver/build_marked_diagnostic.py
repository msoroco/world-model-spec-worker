"""Build a textual, source-shaped marked-turn diagnostic for the first case."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__indicated_course'


def put(path, value, compact=False):
    options = {'separators': (',', ':')} if compact else {'indent': 2}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, **options) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def build():
    # The supplied example's trace is straight and remote from its video pixels.
    # This previously proved textual fixture has a turn-shaped nine-frame trace;
    # only the marked-course originals below serve this law's measurements.
    spec = json.loads((REPO / 'work/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver'
                       / 'vehicle-indicator-diagnostic.json').read_text())
    frames = [json.loads(line) for line in spec['files']['video_frames.jsonl'].splitlines() if line]
    trace = [json.loads(line) for line in spec['files']['trace.jsonl'].splitlines() if line]
    if len(frames) != len(trace) or len(frames) < 3:
        raise ValueError('Supplied textual fixture has no joined turn path')
    authority = {
        'municipal_jurisdiction_source': 'CPU diagnostic jurisdiction claim; unverified',
        'intersection_source': 'CPU diagnostic polygon; unverified',
        'authorization_source': 'CPU diagnostic marker claim; unverified',
        'median_opening_with_intersecting_road': True,
        'intersection_polygon_xy_m': [[-3, -3], [10, -3], [10, 9], [-3, 9]],
        'indicated_course_xy_m': [[-8, 0], [0, 0], [8, 6]],
    }
    authority_text = json.dumps(authority, sort_keys=True) + '\n'
    scene = dict(authority, case_id=CASE, ego_actor_id=7,
                 physical_markers_xy_m=[[0, 0]],
                 authority_source_sha256=sha256(authority_text.encode()).hexdigest(),
                 authorization_verified_by_worker=False)
    body = []
    for map_row, trace_row in zip(frames, trace):
        if (map_row['carla_frame'], map_row['time_s']) != (trace_row['frame'], trace_row['time_s']):
            raise ValueError('Supplied textual fixture frame join differs')
        x, y = trace_row['position_m'][:2]
        body.append({'frame': trace_row['frame'], 'time_s': trace_row['time_s'],
                     'actor_id': 7,
                     'corners_xy_m': [[x - .5, y - .5], [x + .5, y - .5],
                                      [x + .5, y + .5], [x - .5, y + .5]]})
    spec['files']['authority_source_original.json'] = authority_text
    spec['files']['marked_intersection.json'] = json.dumps(scene) + '\n'
    spec['files']['turn_body.jsonl'] = ''.join(json.dumps(row) + '\n' for row in body)
    spec['files']['fixture-provenance.json'] = json.dumps({
        'scope': 'CPU software diagnostic only', 'municipal_authority_verified': False,
        'actual_native_capture': False, 'physical_marker_pixels_verified': False}) + '\n'
    diagnostic_path = ROOT / 'indicated-diagnostic.json'
    diagnostic_hash = put(diagnostic_path, spec, compact=True)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': f'work/{ROOT.name}/{diagnostic_path.name}',
                           'sha256': diagnostic_hash}],
              'generator': {'source': f'work/{ROOT.name}/{diagnostic_path.name}',
                            'sha256': diagnostic_hash}}
    put(ROOT / 'indicated-recipe.json', recipe)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['requirement_dispositions'] = [{
        'requirement': plan['law_text'].strip(),
        'source': f'inputs/{ROOT.name}/assignment.json',
        'status': 'selected_required',
        'case_ids': [item['case_id'] for item in plan['cases']],
        'evidence_or_gap': 'No source-backed municipal authority or original marked-turn recording; CPU diagnostic is not legal or physical evidence.'}]
    put(plan_path, plan)
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
        'requirements': [{'disposition_index': 0, 'requirement': plan['law_text'].strip(),
            'source': f'inputs/{ROOT.name}/assignment.json',
            'output_key': 'original_marked_turn_course',
            'method': 'measure_marked_course', 'value_type': 'object', 'kind': 'measured',
            'inputs': ['marked_intersection.json', 'authority_source_original.json',
                       'turn_body.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                       'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                       'driver_reference.mkv']}],
        'negative': {'remove': ['authority_source_original.json'],
                     'error_contains': 'Missing required source: authority_source_original.json'}}
    put(ROOT / 'indicated-measurement-contract.json', contract)
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    entry['measurement_contract'] = 'indicated-measurement-contract.json'
    entry['fixture_recipe'] = f'work/{ROOT.name}/indicated-recipe.json'
    divergent_case = ROOT.name + '__divergent_course'
    divergent = json.loads(json.dumps(spec))
    divergent_scene = dict(scene, case_id=divergent_case)
    divergent['files']['marked_intersection.json'] = json.dumps(divergent_scene) + '\n'
    divergent_bodies = [json.loads(line) for line in divergent['files']['turn_body.jsonl'].splitlines() if line]
    divergent_trace = [json.loads(line) for line in divergent['files']['trace.jsonl'].splitlines() if line]
    divergent_evidence = [json.loads(line) for line in divergent['files']['capture/evidence.jsonl'].splitlines() if line]
    for body_row, trace_row, evidence_row in zip(divergent_bodies[-3:], divergent_trace[-3:], divergent_evidence[-3:]):
        for corner in body_row['corners_xy_m']:
            corner[1] += 2.0
        trace_row['position_m'][1] += 2.0
        trace_row['position']['y'] += 2.0
        evidence_row['ego']['position_m'][1] += 2.0
        for vertex in evidence_row['ego']['body_vertices_m']:
            vertex[1] += 2.0
    divergent['files']['turn_body.jsonl'] = ''.join(json.dumps(row) + '\n' for row in divergent_bodies)
    divergent['files']['trace.jsonl'] = ''.join(json.dumps(row) + '\n' for row in divergent_trace)
    divergent['files']['capture/evidence.jsonl'] = ''.join(json.dumps(row) + '\n' for row in divergent_evidence)
    capture_manifest = json.loads(divergent['files']['capture/manifest.json'])
    capture_manifest['sources']['trace.jsonl'] = sha256(divergent['files']['trace.jsonl'].encode()).hexdigest()
    divergent['files']['capture/manifest.json'] = json.dumps(capture_manifest) + '\n'
    divergent_path = ROOT / 'divergent-diagnostic.json'
    divergent_hash = put(divergent_path, divergent, compact=True)
    divergent_recipe = json.loads(json.dumps(recipe).replace('indicated-diagnostic.json', divergent_path.name))
    for source in divergent_recipe['sources']:
        source['sha256'] = divergent_hash
    divergent_recipe['generator']['sha256'] = divergent_hash
    put(ROOT / 'divergent-recipe.json', divergent_recipe)
    divergent_contract = json.loads(json.dumps(contract).replace(CASE, divergent_case))
    put(ROOT / 'divergent-measurement-contract.json', divergent_contract)
    divergent_entry = next(item for item in manifest['cases'] if item['case_id'] == divergent_case)
    divergent_entry['measurement_contract'] = 'divergent-measurement-contract.json'
    divergent_entry['fixture_recipe'] = f'work/{ROOT.name}/divergent-recipe.json'
    put(manifest_path, manifest)
    construction = json.loads((ROOT / entry['construction']).read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    proposal = {'format': 'worker-semantic-cases', 'status': 'partial',
        'cell_id': 'C126064', 'actor': 'motor_vehicle_driver',
        'cases': [{'case_id': CASE, 'target_law_id': 'LVMC-11-12-020',
            'target_type': 'boundary_probe',
            'rationale': 'Source-shaped indicated-course construction; municipal authority and original motion remain unverified.',
            'variable_assignments': {'turn_course': {'kind': 'controller', 'value': 'indicated'}},
            'unresolved_judgment_calls': ['authorized indications', 'disobey direction'],
            'recording_description': config['case']['recording_description']},
            {'case_id': divergent_case, 'target_law_id': 'LVMC-11-12-020',
             'target_type': 'boundary_probe',
             'rationale': 'Source-shaped divergent body course with the same unverified marker and authority claim.',
             'variable_assignments': {'turn_course': {'kind': 'controller', 'value': 'divergent'}},
             'unresolved_judgment_calls': ['authorized indications', 'disobey direction'],
             'recording_description': config['case']['recording_description']}],
        'sweep_specs': [], 'sweeps_expanded': False}
    put(ROOT / 'proposals/cases.json', proposal)
    return {'case': CASE, 'diagnostic_sha256': diagnostic_hash,
            'divergent_case': divergent_case, 'divergent_diagnostic_sha256': divergent_hash}


if __name__ == '__main__':
    print(build())
