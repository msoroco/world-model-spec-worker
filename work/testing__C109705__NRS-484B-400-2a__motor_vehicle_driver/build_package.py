"""Build frozen exact-case pilot bundles from the local assignment input."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
INPUT = REPO / 'inputs' / AID / 'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def road(root, ident, x, y, heading, length, junction='-1', curvature=None):
    r = ET.SubElement(root, 'road', {'name': 'pilot_%s' % ident, 'id': str(ident),
                                    'length': str(length), 'junction': junction})
    ET.SubElement(r, 'link')
    view = ET.SubElement(r, 'planView')
    geometry = ET.SubElement(view, 'geometry', {'s': '0', 'x': str(x), 'y': str(y),
        'hdg': str(heading), 'length': str(length)})
    ET.SubElement(geometry, 'line' if curvature is None else 'arc',
                  {} if curvature is None else {'curvature': str(curvature)})
    elevation = ET.SubElement(r, 'elevationProfile')
    ET.SubElement(elevation, 'elevation', {'s': '0', 'a': '0', 'b': '0', 'c': '0', 'd': '0'})
    lanes = ET.SubElement(r, 'lanes')
    ET.SubElement(lanes, 'laneOffset', {'s': '0', 'a': '0', 'b': '0', 'c': '0', 'd': '0'})
    section = ET.SubElement(lanes, 'laneSection', {'s': '0'})
    for side, ids in [('left', (1, 2)), ('right', (-1, -2))]:
        bank = ET.SubElement(section, side)
        for lane_id in ids:
            lane = ET.SubElement(bank, 'lane', {'id': str(lane_id), 'type': 'driving', 'level': 'false'})
            ET.SubElement(lane, 'link')
            ET.SubElement(lane, 'width', {'sOffset': '0', 'a': '3.5', 'b': '0', 'c': '0', 'd': '0'})
            ET.SubElement(lane, 'roadMark', {'sOffset': '0', 'type': 'broken' if abs(lane_id) == 1 else 'solid',
                'weight': 'standard', 'color': 'white', 'width': '.12', 'laneChange': 'both'})
    centre = ET.SubElement(section, 'center')
    lane = ET.SubElement(centre, 'lane', {'id': '0', 'type': 'none', 'level': 'false'})
    ET.SubElement(lane, 'roadMark', {'sOffset': '0', 'type': 'solid', 'weight': 'standard',
                                    'color': 'yellow', 'width': '.12', 'laneChange': 'none'})
    return r


def scene():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', {'revMajor': '1', 'revMinor': '4', 'name': 'C109705-400-2a-two-directional',
        'version': '1', 'date': '2026-10-28', 'north': '80', 'south': '-80', 'east': '80',
        'west': '-80', 'vendor': 'worker-demo-test-first-run-v3'})
    approach = road(root, 1, -80, 0, 0, 73)
    east = road(root, 2, 7, 0, 0, 73)
    north = road(root, 3, 0, 7, math.pi/2, 73)
    south = road(root, 4, 0, -80, math.pi/2, 73)
    turn = road(root, 13, -7, 0, 0, 7*math.pi/2, junction='100', curvature=1/7)
    for r, relation, kind, target in [(approach, 'successor', 'junction', '100'),
                                      (east, 'predecessor', 'junction', '100'),
                                      (north, 'predecessor', 'junction', '100'),
                                      (south, 'successor', 'junction', '100'),
                                      (turn, 'predecessor', 'road', '1'),
                                      (turn, 'successor', 'road', '3')]:
        ET.SubElement(r.find('link'), relation, {'elementType': kind, 'elementId': target})
    junction = ET.SubElement(root, 'junction', {'id': '100', 'name': 'C109705'})
    connection = ET.SubElement(junction, 'connection', {'id': '0', 'incomingRoad': '1',
        'connectingRoad': '13', 'contactPoint': 'start'})
    for lane_id in (-1, -2, 1, 2):
        ET.SubElement(connection, 'laneLink', {'from': str(lane_id), 'to': str(lane_id)})
    (ROOT / 'intersection.xodr').write_text(ET.tostring(root, encoding='unicode') + '\n')


def main():
    assignment = json.loads(INPUT.read_text())
    scene()
    runtime = REPO / 'runtime/main-pipeline-v1'
    cases = []
    channel_specs = [
        ('kin.position', 'structured', 'original actor world XYZ'),
        ('kin.heading', 'deg', 'original actor world yaw'),
        ('kin.speed', 'm/s', 'original actor velocity norm'),
        ('road_geometry', 'structured', 'native map projection, topology and map context'),
        ('turn_history', 'structured', 'original pose, heading and route progress')]
    description = {'channels': [{'name': name, 'unit': unit, 'sampling_rate_hz': 20,
        'method': method, 'time_window': 'all original recorded ticks',
        'reference_frame': 'CARLA world / native OpenDRIVE',
        'uncertainty': 'native finite sampling; legal nearest-centerline boundary unresolved'}
        for name, unit, method in channel_specs], 'context_inputs': [],
        'limitations': ['A diagnostic fixture cannot prove left-turn motion, physical right-half position, or camera legibility.']}
    for label, lateral in [('near_center', 1.75), ('far_from_center', 5.25)]:
        cases.append({'case_id': AID + '__' + label, 'target_law_id': assignment['law_id'],
            'target_type': 'boundary_probe',
            'rationale': 'Freeze one approach lateral placement; measure original pose and compare with paired placement without declaring legal cutoff.',
            'variable_assignments': {'approach_lateral_m': {'value': lateral, 'unit': 'm', 'kind': 'controller'}},
            'unresolved_judgment_calls': ['nearest the centerline has no selected statutory lateral threshold',
                                          'public-highway status is synthetic context'],
            'recording_description': description})
    proposal = {'status': 'draft', 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
                'sweep_specs': [], 'cases': cases}
    write(ROOT / 'proposals/cases.json', proposal)
    source_mapping = {
        'drv.turning': ('Original heading and pose bracket the commanded left turn.', ['turn_history', 'kin.heading', 'kin.position']),
        'st.intersection': ('Original native map projection and junction topology identify the crossed junction.', ['road_geometry']),
        'st.lane_enters': ('Original lane projection and native road-connection graph establish incoming approach.', ['road_geometry']),
        'st.centre_line': ('Authored two-way center road mark plus original lateral pose locate the centerline.', ['road_geometry', 'kin.position']),
        'rel.occupies': ('Original full body and lane geometry determine the right-half footprint.', ['road_geometry', 'kin.position']),
        'kin.position': ('Original actor world XYZ history is sampled at every tick.', ['kin.position']),
        'st.one_way_roadway': ('Native two-directional lane inventory and road markings are acquired, not inferred from a weather label.', ['road_geometry']),
        'st.lane_direction': ('Original lane-sign direction is acquired from native map projection and topology.', ['road_geometry'])}
    mapping = {term: {'evidence': evidence, 'channels': channels,
                      'source_refs': ['intersection.xodr', 'capture/evidence.jsonl']}
               for term, (evidence, channels) in source_mapping.items()}
    plan = {'assignment_id': AID, 'actor': assignment['actor'], 'cell_id': assignment['cell_id'],
        'law_id': assignment['law_id'], 'cases': cases,
        'comparisons': [{'case_ids': [c['case_id'] for c in cases],
                         'deliberate_differences': ['approach_lateral_m: 1.75 m versus 5.25 m'],
                         'fixed_conditions': ['same two-directional authored junction', 'same vehicle blueprint',
                                              'same commanded speed and cameras']}],
        'observations': [{'name': name, 'mandatory': True, 'description': method}
                         for name, _, method in channel_specs],
        'source_observation_mapping': mapping,
        'sources': [{'path': str(INPUT.relative_to(REPO)), 'sha256': sha(INPUT)},
                    {'path': 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
                     'sha256': sha(runtime / 'SOURCE-MANIFEST.json')},
                    {'path': 'skills/worker-preparation/SKILL.md',
                     'sha256': sha(REPO / 'skills/worker-preparation/SKILL.md')}],
        'existing_evidence': assignment['existing_evidence'],
        'runtime_uncertainties': ['native connector continuity', 'actual body footprint',
                                  'achieved target approach placement', 'four-camera visibility',
                                  'public vehicular access is a synthetic authored assumption']}
    write(ROOT / 'case-plan.json', plan)
    base_config = {'law_id': assignment['law_id'], 'cell_id': assignment['cell_id'],
        'actor': assignment['actor'], 'supported_case_ids': [c['case_id'] for c in cases],
        'required_atoms': ['kin.position', 'kin.heading', 'kin.speed'],
        'authored_test_context': {'public_way_road_ids': [1, 2, 3, 4, 13],
            'core_assumptions': [['asm.public_highway', True]],
            'public_highway_provenance': 'Synthetic authoring only; no administrative dedication record in this worker',
            'two_directional_authoring': 'Each intersecting highway has signed left and right driving lanes; verify native direction and physical geometry.'},
        'public_way_road_ids': [],
        'target_speed_mps': 5.0, 'max_ticks': 500,
        'cameras': [{'width': 1920, 'height': 1080, 'x': -8, 'y': 0, 'z': 35, 'pitch': -80, 'yaw': 0},
                    {'width': 1280, 'height': 720, 'x': 2, 'y': 0, 'z': 4, 'pitch': -10, 'yaw': 0},
                    {'width': 1280, 'height': 720, 'x': -4, 'y': -8, 'z': 5, 'pitch': -12, 'yaw': 25},
                    {'width': 1280, 'height': 720, 'x': 7, 'y': -3, 'z': 8, 'pitch': -35, 'yaw': 90}]}
    config = dict(base_config, case=cases[0], selected_case_id=cases[0]['case_id'])
    write(ROOT / 'config.json', config)
    common_paths = ['runner.py', 'analyze.py', 'intersection.xodr', 'tests/test_pilot.py']
    def construction(case):
        selected = dict(base_config, case=case, selected_case_id=case['case_id'])
        files = [{'path': path, 'content': (ROOT / path).read_text(),
                  'source': str((ROOT / path).relative_to(REPO))} for path in common_paths]
        files.append({'path': 'config.json', 'content': json.dumps(selected, indent=2) + '\n'})
        return {'case_id': case['case_id'], 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
                'entrypoint': 'runner.py', 'recording_description': description,
                'measurement_plan': 'Original pose/heading/footprint versus two fixed approach offsets; no legal cutoff.',
                'static_checks': ['authored OpenDRIVE geometry', 'source identity joins', 'camera configuration'],
                'termination_rules': ['measured northbound route endpoint or max 500 ticks'],
                'mechanisms': ['configuration-driven controller', 'native PipelineCapture', 'four RGB views'],
                'files': files}
    write(ROOT / 'construction.json', construction(cases[0]))
    entries = []
    for case in cases:
        path = ROOT / 'constructions' / (case['case_id'] + '.json')
        write(path, construction(case))
        acquisition = {name: {'entrypoint': 'runner.py',
                              'method': 'Original same-frame actor/map/camera acquisition, finalized by analyze.py',
                              'evidence': ['trace.jsonl', 'capture/evidence.jsonl', 'channels/' + name + '.jsonl']}
                       for name, _, _ in channel_specs}
        entries.append({'case_id': case['case_id'], 'kind': 'capability',
            'construction': str(path.relative_to(ROOT)), 'construction_sha256': sha(path),
            'measurement_procedure': {'entrypoint': 'analyze.py', 'output_schema': 'pilot-approach-capability-v1'},
            'acquisition': acquisition})
    write(ROOT / 'execution-manifest.json', {'format': 'worker-execution-manifest-v1',
          'assignment_id': AID, 'runtime_manifest_sha256': sha(runtime / 'SOURCE-MANIFEST.json'),
          'cases': entries})


if __name__ == '__main__':
    main()
