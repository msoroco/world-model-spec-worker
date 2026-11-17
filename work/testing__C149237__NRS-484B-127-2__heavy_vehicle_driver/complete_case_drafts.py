"""Bind the eight constructed cases to canonical draft parameters and probe metadata."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent
PATH = ROOT / 'proposals/cases.json'
INDEX = ROOT / 'proposals/semantic-index.json'
PREFIX = ROOT.name + '__'


def assignment(kind, value, unit):
    return {'kind': kind, 'value': value, 'unit': unit}


def main():
    data = json.loads(PATH.read_text())
    cases = [case for case in data['cases'] if case['target_type'] != 'baseline']
    description = deepcopy(cases[0]['recording_description'])
    defaults = {
        'requested_body_gap_m': assignment('world_setup', 152.4, 'm'),
        'ego_target_speed_mps': assignment('controller', 12.0, 'm/s'),
        'lead_target_speed_mps': assignment('controller', 12.0, 'm/s'),
        'same_direction_lane_count': assignment('world_setup', 1, 'count'),
        'requested_ego_width_m': assignment('world_setup', 2.032, 'm'),
        'requested_lead_width_m': assignment('world_setup', 2.032, 'm'),
        'passing_lane_id': assignment('world_setup', 0, 'id'),
        'longitudinal_body_gap': assignment('subject_behavior', None, 'm'),
        'ego_overall_width': assignment('subject_behavior', None, 'm'),
        'lead_overall_width': assignment('subject_behavior', None, 'm')}
    baseline = {'case_id': PREFIX + 'baseline', 'target_law_id': 'NRS-484B-127-2',
                'target_type': 'baseline', 'rationale': 'Shared engineering setup, with legal status unresolved.',
                'variable_assignments': deepcopy(defaults),
                'recording_description': deepcopy(description),
                'unresolved_judgment_calls': ['whenever conditions permit', 'without danger']}
    mappings = {
        'gap_below_500ft': ('gap', 'below', 150 / .3048),
        'gap_at_500ft': ('gap', 'at', 500),
        'gap_above_500ft': ('gap', 'above', 155 / .3048),
        'ego_width_below_80in': ('ego_width', 'below', 2.0 / .0254),
        'ego_width_at_80in': ('ego_width', 'at', 80),
        'lead_width_below_80in': ('lead_width', 'below', 2.0 / .0254)}
    paths = {'gap': ('obligation.numeric_conditions[0]', 'longitudinal_body_gap', 'ft', 'requested_body_gap_m'),
             'ego_width': ('activation.numeric_conditions[0]', 'ego_overall_width', 'in', 'requested_ego_width_m'),
             'lead_width': ('activation.numeric_conditions[1]', 'lead_overall_width', 'in', 'requested_lead_width_m')}
    for case in cases:
        suffix = case['case_id'].removeprefix(PREFIX)
        original = case['variable_assignments']
        case['variable_assignments'] = deepcopy(defaults)
        case['variable_assignments'].update(original)
        case['unresolved_judgment_calls'] = ['whenever conditions permit', 'without danger']
        if suffix in mappings:
            group, side, test_value = mappings[suffix]
            path, primary, unit, difference = paths[group]
            case.update(target_type='boundary_probe', paired_probe_id='truck_follow_' + group,
                        deliberate_differences=[difference],
                        epsilon_used={'value': 1 if unit == 'ft' else .5, 'unit': unit,
                                      'rationale': 'Engineering sampling margin; no legal tolerance.'},
                        probe={'primary_variable': primary,
                               'comparison_or_standard': 'exact statutory boundary; physical value awaits Native readback',
                               'target_value_or_branch': side, 'threshold_ref': path,
                               'operator': '>=', 'unit': unit, 'test_value': test_value})
        else:
            case.update(target_type='judgment_sweep', paired_probe_id='truck_follow_exceptions',
                        deliberate_differences=['same_direction_lane_count', 'ego_target_speed_mps',
                                                'lead_target_speed_mps', 'passing_lane_id', 'requested_body_gap_m'],
                        probe={'primary_variable': 'same_direction_lane_count' if suffix == 'two_same_direction_lanes' else 'passing_lane_id',
                               'comparison_or_standard': 'source-law exception branch',
                               'target_value_or_branch': suffix})
    data.update(cell_id='C149237', actor='heavy_vehicle_driver', status='draft',
                cases=[baseline] + cases,
                sweep_specs=[{'sweep_id': 'truck_follow_qualitative_review',
                              'target_law_id': 'NRS-484B-127-2',
                              'judgment_refs': [
                                  {'phrase': 'whenever conditions permit',
                                   'note': 'Road, traffic, visibility, and continuity require original-source review.'},
                                  {'phrase': 'without danger',
                                   'note': 'Safe entry and occupancy by an overtaking vehicle require original-source review.'}],
                              'rationale': 'Original-source judgment review remains to be physically sampled.',
                              'status': 'incomplete',
                              'missing_inputs': ['Native physical capture, reviewed overtaker occupancy, and verified road context']}] )
    PATH.write_text(json.dumps(data, indent=2) + '\n')
    index = json.loads(INDEX.read_text())
    index['stages']['cases']['sha256'] = hashlib.sha256(PATH.read_bytes()).hexdigest()
    INDEX.write_text(json.dumps(index, indent=2) + '\n')


def build_combination_draft():
    """Materialize an unselected exact 500-foot combination CPU construction."""
    source = json.loads((ROOT / 'gap-constructions/gap_at_500ft.json').read_text())
    draft = deepcopy(source)
    case_id = PREFIX + 'combination_at_500ft'
    draft['case_id'] = case_id
    files = {row['path']: row for row in draft['files']}

    def change(name, old, new):
        row = files[name]
        if row['content'].count(old) != 1:
            raise ValueError('Combination draft source anchor changed: ' + name)
        row['content'] = row['content'].replace(old, new)
        row.pop('source', None)

    config = json.loads(files['config.json']['content'])
    config['selected_case_id'] = case_id
    config['supported_case_ids'].append(case_id)
    config['combination_trailer_blueprint_id'] = 'vehicle.ford.crown'
    config['required_atoms'].append('ru.trailer_or_combination')
    for channel in config['recording_description']['channels']:
        if channel['name'] in ('ego_overall_width', 'lead_overall_width'):
            channel['method'] = 'original Native tractor and attached-vehicle body envelope'
    files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
    files['config.json'].pop('source', None)
    draft['recording_description'] = deepcopy(config['recording_description'])
    files['combination_construction.py'] = {
        'path': 'combination_construction.py',
        'content': (ROOT / 'combination_construction.py').read_text()}
    draft['files'].append(files['combination_construction.py'])

    change('runner.py', 'from truck_capture_sources import record_sample',
           'from truck_capture_sources import record_sample, record_combination_sample')
    change('runner.py', 'from truck_construction import spawn_exact_gap_pair',
           'from truck_construction import spawn_exact_gap_pair\n'
           'from combination_construction import spawn_combination_pair')
    change('runner.py', "suffix not in GAP_TARGETS_M and suffix not in WIDTH_CASES and suffix not in ('two_same_direction_lanes','overtaking')",
           "suffix not in GAP_TARGETS_M and suffix not in WIDTH_CASES and suffix not in ('two_same_direction_lanes','overtaking','combination_at_500ft')")
    change('runner.py', 'if selected_case in GAP_TARGETS_M:\n            pair_context=spawn_exact_gap_pair',
           "if selected_case == 'combination_at_500ft':\n"
           "            trailer_bp = bp.find(config['combination_trailer_blueprint_id'])\n"
           "            if trailer_bp is None or trailer_bp.id != 'vehicle.ford.crown':\n"
           "                raise ValueError('Reviewed towed-vehicle blueprint missing')\n"
           "            truck_bps = {'ego': {'tractor': ego_bp, 'trailer': trailer_bp},\n"
           "                         'lead': {'tractor': lead_bp, 'trailer': trailer_bp}}\n"
           "            poses = {role: {'tractor': transform_at(x, -1.9, 0.),\n"
           "                            'trailer': carla.Transform(carla.Location(x=-10., y=0., z=0.),\n"
           "                                                       carla.Rotation())}\n"
           "                     for role, x in (('ego', 100.), ('lead', 300.))}\n"
           "            def position_lead(actors, delta, tangent):\n"
           "                pose = actors['tractor'].get_transform()\n"
           "                pose.location.x += delta * tangent[0]\n"
           "                pose.location.y += delta * tangent[1]\n"
           "                actors['tractor'].set_transform(pose)\n"
           "            pair_context=spawn_combination_pair(\n"
           "                world, truck_bps, poses, carla.AttachmentType.Rigid,\n"
           "                road_id=149237, lane_id=-1, lane_forward_xy=[1., 0.],\n"
           "                expected_body_gap_m=152.4, gap_tolerance_m=.5,\n"
           "                position_lead=position_lead)\n"
           "        elif selected_case in GAP_TARGETS_M:\n            pair_context=spawn_exact_gap_pair")
    change('runner.py', "ego, lead = pair['ego'], pair['lead']\n            context =",
           "if selected_case == 'combination_at_500ft':\n"
           "                ego, lead = pair['actors']['ego']['tractor'], pair['actors']['lead']['tractor']\n"
           "                site = validate_site()\n"
           "            else:\n"
           "                ego, lead = pair['ego'], pair['lead']\n"
           "                site = pair['site']\n"
           "            context =")
    for key in ('road_id', 'lane_id', 'same_direction_lane_count', 'road_sha256'):
        files['runner.py']['content'] = files['runner.py']['content'].replace("pair['site']['" + key + "']", "site['" + key + "']")
    change('runner.py', "'overall_width_limit': 'single vehicles; Native bounding boxes, no trailer claim'",
           "'overall_width_limit': ('attached vehicle body envelopes; legal class unverified'\n"
           "                                                if selected_case == 'combination_at_500ft' else\n"
           "                                                'single vehicles; Native bounding boxes, no trailer claim')")
    change('runner.py', "context = {'native_map_id': mapping.name,",
           "context = {'source_kind': 'original_native', 'native_map_id': mapping.name,")
    change('runner.py', 'record_sample(frame_map, history, snap, ego, lead, ego_wp, lead_wp)',
           "if selected_case == 'combination_at_500ft':\n"
           "                                record_combination_sample(frame_map, history, snap, pair['actors'],\n"
           "                                                          mapping, site['road_id'], site['lane_id'])\n"
           "                            else:\n"
           "                                record_sample(frame_map, history, snap, ego, lead, ego_wp, lead_wp)")
    change('truck_capture_sources.py', 'import math\n',
           'import math\nfrom combination_construction import combination_source_row, audit_combination_source_row\n')
    files['truck_capture_sources.py']['content'] += '''\n\ndef record_combination_sample(frame_map, history_stream, snapshot, groups, mapping, road_id, lane_id):
    waypoints = {role: {part: mapping.get_waypoint(actor.get_location(), project_to_road=False)
                        for part, actor in actors.items()} for role, actors in groups.items()}
    row = combination_source_row(groups, waypoints, [1., 0.], road_id, lane_id,
                                 snapshot.frame, snapshot.timestamp.elapsed_seconds)
    audit_combination_source_row(row, [1., 0.], road_id, lane_id)
    mapping_row = frame_map.append(row['frame'], row['time_s'])
    history_stream.write(json.dumps(row, allow_nan=False) + '\\n')
    return {'video_frame': mapping_row['video_frame'], 'frame': row['frame']}
'''
    change('finalizer.py', 'from truck_measurements import analyze',
           'from truck_measurements import analyze\n'
           'from combination_construction import audit_combination_source_row')
    change('finalizer.py', "'gap_above_500ft': 155.0}",
           "'gap_above_500ft': 155.0, 'combination_at_500ft': 152.4}")
    change('finalizer.py', "suffix not in GAP_TARGETS_M and suffix not in WIDTH_CASES and suffix not in ('two_same_direction_lanes','overtaking')",
           "suffix not in GAP_TARGETS_M and suffix not in WIDTH_CASES and suffix not in ('two_same_direction_lanes','overtaking','combination_at_500ft')")
    change('finalizer.py', 'report = analyze(attempt)',
           "rows = [json.loads(line) for line in (attempt/'truck_history.jsonl').read_text().splitlines() if line.strip()]\n"
           "    context = json.loads((attempt/'road_context.json').read_text())\n"
           "    if context.get('source_kind') == 'original_native' and len(rows) != 900:\n"
           "        raise ValueError('Incomplete original combination frame history')\n"
           "    for row in rows:\n"
           "        audit_combination_source_row(row, context['lane_forward_xy'],\n"
           "                                     context['road_id'], context['lane_id'])\n"
           "    report = analyze(attempt)")
    change('tests/test_bundle.py', "{'two_same_direction_lanes','overtaking'}",
           "{'two_same_direction_lanes','overtaking','combination_at_500ft'}")
    files['tests/test_bundle.py']['content'] = files['tests/test_bundle.py']['content'].replace(
        "\nif __name__ == '__main__':", '''\n    def test_combination_source_is_packaged(self):
        config = json.loads(Path(runner.__file__).with_name('config.json').read_text())
        self.assertEqual(config['combination_trailer_blueprint_id'], 'vehicle.ford.crown')
        self.assertIn('ru.trailer_or_combination', config['required_atoms'])
        source = Path(runner.__file__).with_name('combination_construction.py').read_text()
        self.assertIn('position_lead(groups["lead"]', source)
        self.assertIn('capture_combination_history', source)
        finalizer = Path(runner.__file__).with_name('finalizer.py').read_text()
        self.assertIn('audit_combination_source_row(row', finalizer)

if __name__ == '__main__':''')
    draft_dir = ROOT.parents[1] / '.runtime-work/c149237-combination-draft'
    draft_dir.mkdir(parents=True, exist_ok=True)
    (draft_dir / 'measurement-contract.json').write_bytes(
        (ROOT / 'measurement-contract.json').read_bytes())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    for index, disposition in enumerate(plan['requirement_dispositions']):
        if index < 3 and disposition['status'] == 'selected_required' and case_id not in disposition.get('case_ids', []):
            disposition.setdefault('case_ids', []).append(case_id)
    (draft_dir / 'case-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    proposals = json.loads((ROOT / 'proposals/cases.json').read_text())
    template_proposal = next(row for row in proposals['cases']
                             if row['case_id'].endswith('__gap_at_500ft'))
    combination_proposal = deepcopy(template_proposal)
    combination_proposal['case_id'] = case_id
    combination_proposal['rationale'] = (
        'Controlled 500-foot following comparison with tractor plus attached '
        'towed vehicle in both subject and lead roles; Native class and coupling unverified.')
    combination_proposal['variable_assignments']['combination_trailer_blueprint_id'] = {
        'kind': 'world_setup', 'value': 'vehicle.ford.crown', 'unit': 'blueprint_id'}
    proposals['cases'].append(combination_proposal)
    (draft_dir / 'proposals').mkdir(exist_ok=True)
    (draft_dir / 'proposals/cases.json').write_text(json.dumps(proposals, indent=2) + '\n')
    construction = draft_dir / 'construction.json'
    construction.write_text(json.dumps(draft, indent=2) + '\n')
    diagnostic = json.loads((ROOT / 'diagnostic-gap_at_500ft.json').read_text())
    history = []
    for line in diagnostic['files']['truck_history.jsonl'].splitlines():
        row = json.loads(line)
        for role, trailer_id in (('ego', 305), ('lead', 306)):
            part = row[role]
            tractor = deepcopy(part['body_vertices_xy_m'])
            if role == 'lead':
                tractor = [[x + 10., y] for x, y in tractor]
            rear = min(x for x, y in tractor)
            ys = sorted({y for x, y in tractor})
            trailer = [[x, y] for x in (rear - 10., rear - 2.) for y in ys]
            part['body_vertices_xy_m'] = tractor + trailer
            part['overall_width_source'] = 'synthetic component diagnostic; not Native geometry'
            part['legal_vehicle_class_verified'] = False
            part['native_attachment_verified'] = False
            part['components'] = {
                'tractor': {'actor_id': part['actor_id'], 'blueprint_id': part['blueprint_id'],
                            'road_id': part['road_id'], 'lane_id': part['lane_id'],
                            'body_vertices_xy_m': tractor},
                'trailer': {'actor_id': trailer_id, 'blueprint_id': 'vehicle.ford.crown',
                            'road_id': part['road_id'], 'lane_id': part['lane_id'],
                            'body_vertices_xy_m': trailer}}
        history.append(json.dumps(row, allow_nan=False))
    diagnostic['files']['truck_history.jsonl'] = '\n'.join(history) + '\n'
    context = json.loads(diagnostic['files']['road_context.json'])
    context['source_kind'] = 'synthetic_diagnostic'
    context['overall_width_limit'] = 'synthetic component envelope; legal class unverified'
    diagnostic['files']['road_context.json'] = json.dumps(context) + '\n'
    capture = json.loads(diagnostic['files']['capture/manifest.json'])
    capture['case_id'] = case_id
    diagnostic['files']['capture/manifest.json'] = json.dumps(capture) + '\n'
    diagnostic_path = ROOT / 'combination-at-500ft-diagnostic.json'
    diagnostic_path.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
    recipe = json.loads((ROOT / 'fixture-recipe-gap_at_500ft.json').read_text())
    recipe['generator'] = {
        'source': str(diagnostic_path.relative_to(ROOT.parents[1])),
        'sha256': hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()}
    recipe_path = draft_dir / 'diagnostic-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    base = json.loads((ROOT / 'execution-manifest.json').read_text())
    template = next(row for row in base['cases'] if row['case_id'].endswith('__gap_at_500ft'))
    entry = deepcopy(template)
    for key in ('candidates', 'offline', 'compatibility', 'negative', 'post_capture',
                'physical_preparation', 'delivery_acceptance', 'native_handoff'):
        entry.pop(key, None)
    entry.update(case_id=case_id, construction='construction.json',
                 construction_sha256=hashlib.sha256(construction.read_bytes()).hexdigest(),
                 fixture_recipe=str(recipe_path.relative_to(ROOT.parents[1])),
                 kind='diagnostic_unselected',
                 candidate_risk={'status': 'physical',
                                 'reason': 'Attached vehicle motion, body gap and cameras unverified'})
    fallback_plans = {
        'fallback1': {
            'path': 'runner.py', 'old': "('lead', 300.)", 'new': "('lead', 340.)",
            'trigger': {'source': 'Native spawn result and capture/evidence.jsonl',
                        'metric': 'lead combination staging spawn and attachment readback',
                        'failure_condition': 'lead component cannot spawn or attach at x=300 m'},
            'changed_knobs': ['lead combination staging origin x=300 m to x=340 m; measured final body gap fixed at 152.4 m']},
        'fallback2': {
            'path': 'runner.py',
            'old': "'reference_corner': static(300, -24, 30, 90, -25)",
            'new': "'reference_corner': static(330, -30, 35, 90, -28)",
            'trigger': {'source': 'reference_corner.mkv',
                        'metric': 'original frames showing both tractor and attached-vehicle bodies',
                        'failure_condition': 'the required reference camera does not show both combinations together'},
            'changed_knobs': ['reference-corner camera origin (300,-24,30) to (330,-30,35) m and pitch -25 to -28 degrees']},
        'fallback3': {
            'path': 'truck_follow_controller.py',
            'old': '0.25 * speed_error', 'new': '0.35 * speed_error',
            'trigger': {'source': 'truck_history.jsonl',
                        'metric': 'original tractor speed error from the 12 m/s engineering target',
                        'failure_condition': 'either tractor misses the target by more than 1 m/s during the following interval'},
            'changed_knobs': ['bounded throttle gain 0.25 to 0.35; target speed and exact case fixed']},
    }
    candidates = []
    candidate_dir = draft_dir / 'candidates'
    candidate_dir.mkdir(exist_ok=True)
    for ident, spec in fallback_plans.items():
        alternate = deepcopy(draft)
        source_file = next(row for row in alternate['files'] if row['path'] == spec['path'])
        if source_file['content'].count(spec['old']) != 1:
            raise ValueError('Combination fallback source anchor changed: ' + ident)
        source_file['content'] = source_file['content'].replace(spec['old'], spec['new'])
        source_file.pop('source', None)
        candidate_path = candidate_dir / (ident + '.json')
        candidate_path.write_text(json.dumps(alternate, indent=2) + '\n')
        candidates.append({'id': ident, 'construction': 'candidates/' + ident + '.json',
                           'construction_sha256': hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
                           'trigger': spec['trigger'], 'changed_knobs': spec['changed_knobs']})
    entry['candidates'] = candidates
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
                'runtime_manifest_sha256': base['runtime_manifest_sha256'],
                'cases': [entry]}
    (draft_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': case_id, 'construction_sha256': manifest['cases'][0]['construction_sha256'],
                      'returned': False, 'selected': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--combination-draft', action='store_true')
    args = parser.parse_args()
    build_combination_draft() if args.combination_draft else main()
