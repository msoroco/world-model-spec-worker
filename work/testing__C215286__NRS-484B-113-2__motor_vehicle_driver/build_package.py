"""Derive this assignment's exact cases and bundled implementation from its frozen input."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
ASSIGNMENT = REPO / 'inputs' / AID / 'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def mode_for(law):
    return {'NRS-484B-257-1': 'signed_yield', 'NRS-484B-257-2': 'signed_non_through',
            'NRS-484B-407': 'curve_u_turn', 'NRS-484B-127-2': 'truck_follow',
            'NRS-484B-113-2': 'reverse_crosswalk'}[law]


def cases_for(mode, assignment, description):
    if mode == 'signed_yield':
        values = [('yield_wait', 1.0, 'slowing/stopping before entry with through traffic'),
                  ('yield_no_wait', 0.0, 'no commanded pre-entry wait with the same through traffic')]
        key, unit, kind = 'requested_wait_s', 's', 'controller'
    elif mode == 'signed_non_through':
        values = [('inside_wait', 1.0, 'vehicle already in the intersection'),
                  ('inside_no_wait', 0.0, 'same vehicle without commanded wait'),
                  ('approach_wait', 1.5, 'counterpart approaching during the crossing')]
        key, unit, kind = 'requested_wait_s', 's', 'controller'
    elif mode == 'curve_u_turn':
        values = [('sight_120m', 120.0, 'sampled below 500 ft'),
                  ('sight_152_4m', 152.4, 'sampled at 500 ft'),
                  ('sight_180m', 180.0, 'sampled beyond 500 ft')]
        key, unit, kind = 'sight_probe_m', 'm', 'world_setup'
    elif mode == 'truck_follow':
        values = [('gap_130m', 130.0, 'below 500 ft body gap'),
                  ('gap_152_4m', 152.4, 'at 500 ft body gap'),
                  ('gap_180m', 180.0, 'above 500 ft body gap')]
        key, unit, kind = 'requested_gap_m', 'm', 'controller'
    else:
        values = [('reverse_outside', 0, 'reverse before crosswalk footprint'),
                  ('reverse_over', 1, 'reverse into crosswalk footprint')]
        key, unit, kind = 'reverse_overlap_target', 'categorical', 'controller'
    output = []
    for label, value, rationale in values:
        variables = {key: {'value': value, 'unit': unit, 'kind': kind}}
        if mode == 'reverse_crosswalk':
            variables['reverse_endpoint_x_m'] = {'value': -5.0 if value else 6.0,
                                                'unit': 'm', 'kind': 'controller'}
        output.append({'case_id': AID + '__' + label,
            'target_law_id': assignment['law_id'], 'target_type': 'boundary_probe',
            'rationale': rationale + '; freeze inputs and measure native evidence without legal labels',
            'variable_assignments': variables,
            'unresolved_judgment_calls': ['Physical motion/scene source verification remains pending',
                'No statutory verdict is selected by this capability probe'],
            'recording_description': description})
    return output


def road(root, ident, x, y, heading, length, lane_sides, *, curvature=None,
         elevation=(0, 0, 0, 0), junction='-1'):
    item = ET.SubElement(root, 'road', {'name': 'partition03_%s' % ident, 'id': str(ident),
                                      'length': str(length), 'junction': junction})
    ET.SubElement(item, 'link')
    view = ET.SubElement(item, 'planView')
    geometry = ET.SubElement(view, 'geometry', {'s': '0', 'x': str(x), 'y': str(y),
        'hdg': str(heading), 'length': str(length)})
    ET.SubElement(geometry, 'line' if curvature is None else 'arc',
                  {} if curvature is None else {'curvature': str(curvature)})
    profile = ET.SubElement(item, 'elevationProfile')
    ET.SubElement(profile, 'elevation', {'s': '0', 'a': str(elevation[0]),
        'b': str(elevation[1]), 'c': str(elevation[2]), 'd': str(elevation[3])})
    lanes = ET.SubElement(item, 'lanes')
    ET.SubElement(lanes, 'laneOffset', {'s': '0', 'a': '0', 'b': '0', 'c': '0', 'd': '0'})
    section = ET.SubElement(lanes, 'laneSection', {'s': '0'})
    for side in ('left', 'right'):
        bank = ET.SubElement(section, side)
        for lane_id in lane_sides.get(side, []):
            lane = ET.SubElement(bank, 'lane', {'id': str(lane_id), 'type': 'driving', 'level': 'false'})
            ET.SubElement(lane, 'link')
            ET.SubElement(lane, 'width', {'sOffset': '0', 'a': '3.5', 'b': '0', 'c': '0', 'd': '0'})
            ET.SubElement(lane, 'roadMark', {'sOffset': '0', 'type': 'broken', 'weight': 'standard',
                'color': 'white', 'width': '.12', 'laneChange': 'both'})
    centre = ET.SubElement(section, 'center')
    ET.SubElement(centre, 'lane', {'id': '0', 'type': 'none', 'level': 'false'})
    return item


def scene(mode):
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', {'revMajor': '1', 'revMinor': '4', 'name': AID,
        'version': '1', 'date': '2026-10-28', 'north': '500', 'south': '-500',
        'east': '1000', 'west': '-500', 'vendor': 'worker-demo-test-first-run-v3'})
    two_way = {'left': [1], 'right': [-1]}
    if mode in ('signed_yield', 'signed_non_through'):
        first = road(root, 1, -100, 0, 0, 95, two_way)
        road(root, 2, 5, 0, 0, 95, two_way)
        approach = road(root, 3, 0, -100, math.pi/2, 95, two_way)
        road(root, 4, 0, 5, math.pi/2, 95, two_way)
        connector = road(root, 13, -5, 0, 0, 10, two_way, junction='100')
        cross_connector = road(root, 14, 0, -5, math.pi/2, 10, two_way, junction='100')
        ET.SubElement(first.find('link'), 'successor', {'elementType': 'junction', 'elementId': '100'})
        ET.SubElement(connector.find('link'), 'predecessor', {'elementType': 'road', 'elementId': '1'})
        ET.SubElement(connector.find('link'), 'successor', {'elementType': 'road', 'elementId': '2'})
        ET.SubElement(approach.find('link'), 'successor', {'elementType': 'junction', 'elementId': '100'})
        ET.SubElement(cross_connector.find('link'), 'predecessor', {'elementType': 'road', 'elementId': '3'})
        ET.SubElement(cross_connector.find('link'), 'successor', {'elementType': 'road', 'elementId': '4'})
        j = ET.SubElement(root, 'junction', {'id': '100', 'name': 'signed entrance'})
        connection = ET.SubElement(j, 'connection', {'id': '0', 'incomingRoad': '1',
            'connectingRoad': '13', 'contactPoint': 'start'})
        ET.SubElement(connection, 'laneLink', {'from': '-1', 'to': '-1'})
        crossing = ET.SubElement(j, 'connection', {'id': '1', 'incomingRoad': '3',
            'connectingRoad': '14', 'contactPoint': 'start'})
        ET.SubElement(crossing, 'laneLink', {'from': '-1', 'to': '-1'})
        signals = ET.SubElement(first, 'signals')
        ET.SubElement(signals, 'signal', {'id': '201', 's': '87', 't': '-3.5', 'name': 'approach_yield',
            'dynamic': 'no', 'orientation': '+', 'type': '205' if mode == 'signed_yield' else '206',
            'subtype': '0', 'value': '0', 'unit': 'none', 'height': '2.0', 'width': '.75'})
    elif mode == 'curve_u_turn':
        road(root, 1, -100, 0, 0, 200, two_way, curvature=1/90,
             elevation=(0, .015, -.00015, .0000003))
    elif mode == 'truck_follow':
        road(root, 1, 0, 0, 0, 1000, {'left': [], 'right': [-1]})
    else:
        item = road(root, 1, -100, 0, 0, 200, two_way)
        objects = ET.SubElement(item, 'objects')
        ET.SubElement(objects, 'object', {'id': '301', 'name': 'authored_crosswalk',
            'type': 'crosswalk', 's': '100', 't': '0', 'zOffset': '0',
            'hdg': '0', 'length': '4', 'width': '10', 'height': '0'})
    (ROOT / 'scene.xodr').write_text(ET.tostring(root, encoding='unicode') + '\n')


CHANNELS = [
    ('kin.position', 'structured', 'original actor world XYZ'),
    ('kin.heading', 'deg', 'original actor world yaw'),
    ('kin.speed', 'm/s', 'original actor velocity norm'),
    ('native_context', 'structured', 'original map/actor inventory and authored context'),
    ('road_geometry', 'structured', 'original map projection and authored region dimensions'),
    ('motion_event', 'structured', 'original route, control, pose, speed and reverse state'),
    ('participant_relation', 'structured', 'original counterpart body and motion'),
    ('visibility_rays', 'structured', 'native finite bidirectional ray samples and subject rays'),
    ('surface_gap', 'structured', 'original full-body longitudinal separation'),
    ('crosswalk_overlap', 'structured', 'original body and authored crossing overlap'),
]


def channel_for(term):
    if term.startswith('kin.'):
        return [term] if term in ('kin.position', 'kin.heading', 'kin.speed') else ['participant_relation']
    if term in ('st.sight_distance', 'rel.visible'):
        return ['visibility_rays', 'road_geometry']
    if term in ('rel.surface_gap', 'rel.ahead_behind_in_lane'):
        return ['surface_gap', 'participant_relation']
    if term == 'rel.occupies':
        return ['crosswalk_overlap', 'road_geometry']
    if term.startswith('dev.') or term.startswith('ru.'):
        return ['native_context', 'participant_relation']
    if term.startswith('st.'):
        return ['road_geometry', 'native_context']
    if term in ('drv.following', 'drv.overtaking', 'drv.yields_to', 'drv.time_to_conflict',
                'drv.approaching', 'drv.in_intersection'):
        return ['participant_relation', 'motion_event']
    return ['motion_event', 'crosswalk_overlap']


def main():
    assignment = json.loads(ASSIGNMENT.read_text())
    mode = mode_for(assignment['law_id'])
    scene(mode)
    description = {'channels': [{'name': name, 'unit': unit, 'sampling_rate_hz': 20,
        'method': method, 'time_window': 'all original recorded ticks',
        'reference_frame': 'CARLA world / native OpenDRIVE',
        'uncertainty': 'finite native sampling; legal threshold or condition remains unresolved'}
        for name, unit, method in CHANNELS], 'context_inputs': [],
        'limitations': ['Three-frame diagnostic data do not prove maneuver completion, scene setup, or pixel visibility.']}
    cases = cases_for(mode, assignment, description)
    proposal = {'status': 'draft', 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
                'sweep_specs': [], 'cases': cases}
    write(ROOT / 'proposals/cases.json', proposal)
    mapping = {item['term']: {'evidence': item['note'] +
        '; measured from original same-frame channels and checked against native source context',
        'channels': channel_for(item['term']),
        'source_refs': ['inputs/'+AID+'/assignment.json', 'capture/evidence.jsonl']}
        for item in assignment['source_observation_terms']}
    plan = {'assignment_id': AID, 'actor': assignment['actor'],
        'cell_id': assignment['cell_id'], 'law_id': assignment['law_id'],
        'cases': cases,
        'comparisons': [{'case_ids': [c['case_id'] for c in cases],
            'deliberate_differences': [next(iter(c['variable_assignments'])) + ': ' +
                str(next(iter(c['variable_assignments'].values()))['value']) for c in cases],
            'fixed_conditions': ['same authored native scene geometry', 'same actor class and camera plan',
                                 'same source acquisition method']}],
        'observations': [{'name': name, 'mandatory': True, 'description': method}
                         for name, _, method in CHANNELS],
        'source_observation_mapping': mapping,
        'sources': [{'path': str(ASSIGNMENT.relative_to(REPO)), 'sha256': sha(ASSIGNMENT)},
                    {'path': 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
                     'sha256': sha(REPO / 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json')},
                    {'path': 'skills/worker-preparation/SKILL.md',
                     'sha256': sha(REPO / 'skills/worker-preparation/SKILL.md')}],
        'existing_evidence': assignment['existing_evidence'],
        'runtime_uncertainties': ['Actual native motion, region/scene appearance, participant positions and duration',
            'Public-way and officer/device authority are explicit synthetic context',
            'Camera framing and statutory judgment remain unverified']}
    write(ROOT / 'case-plan.json', plan)
    cameras = [{'width': 1920, 'height': 1080, 'x': -8, 'y': 0, 'z': 35, 'pitch': -80, 'yaw': 0},
               {'width': 1280, 'height': 720, 'x': 2, 'y': 0, 'z': 4, 'pitch': -10, 'yaw': 0},
               {'width': 1280, 'height': 720, 'x': -4, 'y': -8, 'z': 5, 'pitch': -12, 'yaw': 25},
               {'width': 1280, 'height': 720, 'x': 7, 'y': -3, 'z': 8, 'pitch': -35, 'yaw': 90}]
    context = {'core_assumptions': [['asm.public_highway', True]],
        'public_highway_provenance': 'synthetic authored assumption; no administrative dedication record',
        'scenario_source': assignment['branch'],
        'legal_conditions': assignment['witness']['required_context'],
        'unverified': 'native physical setup and legal status remain operator checks'}
    config = {'law_id': assignment['law_id'], 'cell_id': assignment['cell_id'],
        'actor': assignment['actor'], 'mode': mode,
        'supported_case_ids': [c['case_id'] for c in cases],
        'required_atoms': ['kin.position', 'kin.heading', 'kin.speed'],
        'authored_test_context': context, 'public_way_road_ids': [],
        'target_speed_mps': 3.0 if mode == 'reverse_crosswalk' else 5.0,
        'other_speed_mps': 5.0, 'max_ticks': 700,
        'ego_blueprint': 'vehicle.carlamotors.firetruck' if mode == 'truck_follow' else 'vehicle.lincoln.mkz_2020',
        'other_blueprint': 'vehicle.carlamotors.firetruck' if mode == 'truck_follow' else 'vehicle.tesla.model3',
        'authored_regions': {'intersection_box_m': [-5, 5, -5, 5],
                             'crosswalk_box_m': [-2, 2, -5, 5]},
        'crosswalk_box_m': [-2, 2, -5, 5],
        'signed_entrances': [{'road_id': 1, 'sign_type': 'yield' if mode == 'signed_yield' else 'stop',
                              'source': 'authored OpenDRIVE signal; native readback pending'}]
            if mode.startswith('signed') else [],
        'cameras': cameras}
    from runner import route
    selected = None
    common_paths = ['runner.py', 'analyze.py', 'scene.xodr', 'tests/test_package.py']
    def construction(case):
        selected_config = dict(config, case=case, selected_case_id=case['case_id'],
                               route_end_m=list(route(config, case)[-1]))
        files = [{'path': path, 'content': (ROOT / path).read_text(),
                  'source': str((ROOT / path).relative_to(REPO))} for path in common_paths]
        files.append({'path': 'config.json', 'content': json.dumps(selected_config, indent=2) + '\n'})
        return {'case_id': case['case_id'], 'cell_id': assignment['cell_id'],
            'actor': assignment['actor'], 'entrypoint': 'runner.py',
            'recording_description': description,
            'measurement_plan': 'Original same-frame route, actor bodies, signs/regions, visibility and source video; no legal verdict',
            'static_checks': ['OpenDRIVE scene structure', 'Core atom preflight', 'four camera contracts',
                              'channel and source identity joins'],
            'termination_rules': ['native route endpoint or max 700 ticks; incomplete retained'],
            'mechanisms': ['configuration-driven native controller', 'PipelineCapture original telemetry and graph',
                           'FrameMap source identities', 'native write_result finalization'],
            'files': files}
    first = cases[0]
    write(ROOT / 'config.json', dict(config, case=first, selected_case_id=first['case_id'],
                                    route_end_m=list(route(config, first)[-1])))
    write(ROOT / 'construction.json', construction(first))
    entries = []
    for case in cases:
        path = ROOT / 'constructions' / (case['case_id'] + '.json')
        write(path, construction(case))
        acquisition = {name: {'entrypoint': 'runner.py',
            'method': method + '; original same-frame capture then analyze.py finalization',
            'evidence': ['trace.jsonl', 'capture/evidence.jsonl',
                         'channels/'+name+'.jsonl']} for name, _, method in CHANNELS}
        entries.append({'case_id': case['case_id'], 'kind': 'capability',
            'construction': str(path.relative_to(ROOT)), 'construction_sha256': sha(path),
            'measurement_procedure': {'entrypoint': 'analyze.py',
                                      'output_schema': 'partition03-capability-report-v1'},
            'acquisition': acquisition})
    runtime = REPO / 'runtime/main-pipeline-v1'
    write(ROOT / 'execution-manifest.json', {'format': 'worker-execution-manifest-v1',
        'assignment_id': AID, 'runtime_manifest_sha256': sha(runtime / 'SOURCE-MANIFEST.json'),
        'cases': entries})


if __name__ == '__main__':
    main()
