"""Build four source-gated two-actor diagnostic bundles and fixture recipes."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

from through_highway import ASSIGNMENT, CASES, ENGINEERING, LAW

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DONOR = ROOT / 'work/testing__C150116__NRS-484B-503__motor_vehicle_driver/diagnostics'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
                               separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('worker file too large: ' + str(path))


def description():
    specs = [
        ('through_highway_designation', 'source context', 'reviewed municipal jurisdiction, through-highway designation and intersection map'),
        ('entering_antecedent', 'm and m/s', 'original entering vehicle approach, route and antecedent yielding observation'),
        ('through_driver_response', 'm and m/s', 'original through-highway driver speed, pose and requested response'),
        ('conflict_traversal', 'frame and m', 'original two-actor conflict-box entry and exit order'),
        ('entering_preentry_pause_s', 's', 'original entering vehicle measured preentry pause'),
        ('through_preentry_min_speed_mps', 'm/s', 'original through driver measured approach speed'),
        ('camera_frame_identity', 'frame ID', 'four synchronized original camera views'),
    ]
    return {'channels': [{'name': name, 'unit': unit, 'method': method, 'sampling_rate_hz': 20,
                          'time_window': 'all 900 original frames', 'reference_frame': 'original Native frame and map',
                          'uncertainty': 'synthetic diagnostic does not establish physical or legal yielding'}
                         for name, unit, method in specs],
            'context_inputs': [],
            'limitations': ['Preceding subsection A satisfaction requires independent original source review.',
                            'Measured slowing and conflict order do not themselves establish legal right-of-way.']}


def site_for(name, source_sha):
    maneuver, _ = CASES[name]
    entering = [[-10, -8, 0], [0, 0, 0], [10, 0, 0]] if maneuver == 'enter' else [[0, -10, 0], [0, 0, 0], [0, 10, 0]]
    return {'case_id': ASSIGNMENT + '__' + name,
            'source_kind': 'synthetic_diagnostic_fixture', 'accepted_original_source': False,
            'law_id': LAW, 'cell_id': 'C179789', 'road_kind': 'paved_road', 'control_kind': 'other_vehicle',
            'map_sha256': source_sha, 'map_name': 'synthetic through-highway protocol',
            'intersection_id': 'synthetic C179789 crossing', 'conflict_box_xy': [-2, -2, 2, 2],
            'municipal_jurisdiction_source': source_sha,
            'through_highway_designation_source': source_sha,
            'intersection_geometry_source': source_sha,
            'entrance_control_source': source_sha, 'antecedent_review_source': source_sha,
            'entering_maneuver': maneuver,
            'routes': {'through': {'road_id': 1, 'lane_id': 1,
                                  'direction_source': source_sha, 'route_source': source_sha,
                                  'waypoints_xyz': [[-10, 0, 0], [0, 0, 0], [10, 0, 0]]},
                       'entering': {'road_id': 2, 'lane_id': 1,
                                    'direction_source': source_sha, 'route_source': source_sha,
                                    'waypoints_xyz': entering}}}


def rows_for(name, site):
    maneuver, response = CASES[name]
    engineering = ENGINEERING.get(name, {})
    release = 200 + round(engineering.get('antecedent_pause_s', 0.0) * 20)
    rows = []
    for index in range(900):
        progress = index / 899
        through_x = -15 + 30 * progress
        entering_progress = max(0.0, (index - release) / (899 - release))
        entering_x = -15 + 30 * entering_progress if maneuver == 'enter' else 0.0
        entering_y = -8 + 8 * min(1.0, entering_progress * 2) if maneuver == 'enter' else -15 + 30 * entering_progress
        rows.append({'frame_index': index, 'native_frame': 100 + index, 'time_s': index / 20,
                     'map_sha256': site['map_sha256'], 'intersection_id': site['intersection_id'],
                     'through': {'actor_id': 101, 'alive': True,
                                 'center_xy': [through_x, 0.0],
                                 'speed_mps': 2.0 if response == 'yield_request' and 300 <= index < 470 else engineering.get('through_approach_speed_mps', 8.0)},
                     'entering': {'actor_id': 202, 'alive': True,
                                  'center_xy': [entering_x, entering_y],
                                  'speed_mps': 5.0 if index >= release else 0.0}})
    return rows


def main():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    exact_ids = [ASSIGNMENT + '__' + name for name in CASES]
    existing = {row['case_id']: row for row in plan['cases']}
    for name in ENGINEERING:
        cid = ASSIGNMENT + '__' + name
        if cid not in existing:
            anchor = 'cross_yield' if name.startswith('antecedent_pause') else 'cross_continue'
            row = copy.deepcopy(existing[ASSIGNMENT + '__' + anchor])
            row['case_id'] = cid
            row['case_key'] = name
            row['purpose'] = 'source-gated engineering judgment probe; no legal threshold or verdict'
            row['engineering_point'] = ENGINEERING[name]
            plan['cases'].append(row)
    if {row['case_id'] for row in plan['cases']} != set(exact_ids):
        raise ValueError('selected case plan differs from two-actor engineering grid')
    comparison_ids = {row['comparison_id'] for row in plan['comparisons']}
    for family in ('antecedent_pause', 'precedence_speed'):
        key = 'engineering_' + family
        if key not in comparison_ids:
            plan['comparisons'].append({'comparison_id': key,
                'case_ids': [ASSIGNMENT + '__' + family + '-' + f'{i:04d}' for i in range(3)],
                'fixed_conditions': ['Same reviewed through-highway, entrance control, two actor routes, camera profile and 20 Hz duration'],
                'deliberate_differences': ['Engineering antecedent pause' if family == 'antecedent_pause' else 'Engineering through approach speed']})
    source = plan['selected_branches'][0]
    plan['selected_branch'] = source['branch']
    plan['requirement_dispositions'] = [{'requirement': source['requirement'], 'source': source['source'],
        'status': 'selected_required', 'case_ids': exact_ids,
        'evidence_or_gap': 'No accepted original recording; reviewed through-highway, entrance and antecedent source packet required at capture.',
        'reason': 'All four selected response and maneuver cases measure original two-actor conflict history; legal antecedent and right-of-way remain unresolved.'}]
    plan['observations'] = [{'name': name, 'mandatory': True} for name in
        ('through_highway_designation', 'entering_antecedent', 'through_driver_response',
         'conflict_traversal', 'entering_preentry_pause_s',
         'through_preentry_min_speed_mps', 'camera_frame_identity')]
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'view': view, 'subject': subject, 'interval': 'all original 900 frames'} for view, subject in zip(
            CAMERAS, ('intersection and both vehicles', 'entering vehicle antecedent approach',
                      'through-highway conflict order', 'through driver response'))]}
    write(plan_path, plan)
    note = HERE / 'diagnostic-source-note.json'
    write(note, {'format': 'c179789-synthetic-source-v1', 'source_kind': 'synthetic_diagnostic_fixture',
                 'accepted_original_source': False, 'case_ids': exact_ids})
    donor_gen = json.loads((DONOR / 'stop_no_passenger-generator.json').read_text())
    desc = description()
    entries = []
    for name in CASES:
        cid = ASSIGNMENT + '__' + name
        site = site_for(name, sha(note))
        config = {'assignment_id': ASSIGNMENT, 'law_id': LAW, 'cell_id': 'C179789',
                  'actor': 'motor_vehicle_driver', 'selected_case_id': cid,
                  'rate_hz': 20, 'duration_s': 45, 'required_atoms': [], 'source_packets': [],
                  'cameras': list(CAMERAS),
                  'case': {'case_id': cid, 'name': name, 'maneuver': CASES[name][0],
                           'response': CASES[name][1], **ENGINEERING.get(name, {}),
                           'recording_description': desc}}
        bundle_test = ('"""Exact two-actor bundle source preflight."""\n'
                       'from runner import check\n\n'
                       'def test_bundle():\n'
                       '    case_id, name = check()\n'
                       '    assert case_id.endswith("__" + name)\n')
        files = {'runner.py': (HERE / 'source_deferred_runner.py').read_text(),
                 'original_runner.py': (HERE / 'original_runner.py').read_text(),
                 'through_highway.py': (HERE / 'through_highway.py').read_text(),
                 'analysis.py': (HERE / 'analysis.py').read_text(),
                 'tests/test_bundle.py': bundle_test,
                 'config.json': json.dumps(config, indent=2) + '\n',
                 'scene.json': json.dumps(site, indent=2) + '\n'}
        construction = {'law_id': LAW, 'cell_id': 'C179789', 'actor': 'motor_vehicle_driver',
                        'case_id': cid, 'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': desc,
                        'files': [{'path': path, 'content': content} for path, content in files.items()]}
        target = HERE / ('construction-' + name + '.json')
        write(target, construction)
        folder = HERE / 'diagnostics' / name
        folder.mkdir(parents=True, exist_ok=True)
        row_path = folder / 'two-actor-rows.json'
        write(row_path, rows_for(name, site), compact=True)
        donor_folder = DONOR / 'stop_no_passenger'
        copied = []
        for relative in ('trace.jsonl', 'video_frames.jsonl',
                         'capture/native/frames.jsonl', 'capture/evidence.jsonl'):
            dest = folder / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(donor_folder / relative, dest)
            copied.append({'path': relative, 'source': str(dest.relative_to(ROOT)), 'sha256': sha(dest)})
        provenance = folder / 'acquisition-provenance.json'
        write(provenance, {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                           'scope': 'source-shaped CPU software diagnostic only'})
        for path in (row_path, note, provenance):
            copied.append({'path': path.name, 'source': str(path.relative_to(ROOT)), 'sha256': sha(path)})
        generator = copy.deepcopy(donor_gen)
        capture = json.loads(generator['files']['capture/manifest.json'])
        capture['case_id'] = cid
        capture['sources']['trace.jsonl'] = sha(folder / 'trace.jsonl')
        generator['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
        gen_path = HERE / 'diagnostics' / (name + '-generator.json')
        write(gen_path, generator, compact=True)
        recipe_path = HERE / 'diagnostics' / (name + '-recipe.json')
        write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': copied,
                            'generator': {'source': str(gen_path.relative_to(ROOT)), 'sha256': sha(gen_path)}})
        contract_path = HERE / 'diagnostics' / (name + '-measurement-contract.json')
        write(contract_path, {'format': 'worker-measurement-contract', 'case_id': cid,
            'requirements': [{'disposition_index': 0, 'requirement': source['requirement'],
                'source': source['source'], 'output_key': 'through_highway_interaction',
                'method': 'measure_through_highway', 'value_type': 'object', 'kind': 'measured',
                'inputs': ['two-actor-rows.json', 'diagnostic-source-note.json']}],
            'negative': {'remove': ['two-actor-rows.json'],
                         'error_contains': 'Missing required source: two-actor-rows.json'}})
        entries.append({'case_id': cid, 'kind': 'delivery', 'construction': target.name,
                        'construction_sha256': sha(target),
                        'fixture_recipe': str(recipe_path.relative_to(ROOT)),
                        'measurement_contract': str(contract_path.relative_to(HERE)),
                        'measurement_procedure': {'entrypoint': 'analysis.py'},
                        'source_gate': 'reviewed original municipal jurisdiction, designation, entrance control, antecedent source and Native capture required',
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'},
                        'candidate_risk': {'status': 'none', 'reason': 'No alternate route or camera pose is justified without a reviewed original intersection survey; primary retains explicit route and visibility failure checks.'},
                        'candidates': []})
    write(HERE / 'execution-manifest.json', {'format': 'worker-execution-manifest',
        'assignment_id': ASSIGNMENT, 'status': 'source_gated_draft',
        'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'), 'cases': entries})
    return len(entries)


if __name__ == '__main__':
    print('two-actor draft cases:', main())
