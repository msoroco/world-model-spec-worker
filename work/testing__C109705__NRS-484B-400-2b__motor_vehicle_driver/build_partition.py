"""Build five fresh partition-01 packages from their exact frozen inputs."""
import hashlib
import json
import math
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
RUNTIME = REPO / 'runtime/main-pipeline-v1'
PILOT = REPO / 'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver'
PARTITION = json.loads((REPO / 'partitions/demo-test-01.json').read_text())['assignment_ids'][1:]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def straight_scene(path):
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', {'revMajor': '1', 'revMinor': '4', 'name': 'partition01-straight-two-way',
        'version': '1', 'date': '2026-10-28', 'north': '50', 'south': '-50', 'east': '100',
        'west': '-100', 'vendor': 'worker-demo-test-first-run-v3'})
    road = ET.SubElement(root, 'road', {'name': 'straight', 'id': '1', 'length': '200', 'junction': '-1'})
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
        {'s': '0', 'x': '-100', 'y': '0', 'hdg': '0', 'length': '200'})
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  {'s': '0', 'a': '0', 'b': '0', 'c': '0', 'd': '0'})
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', {'s': '0', 'a': '0', 'b': '0', 'c': '0', 'd': '0'})
    section = ET.SubElement(lanes, 'laneSection', {'s': '0'})
    for side, signs in [('left', (1, 2)), ('right', (-1, -2))]:
        bank = ET.SubElement(section, side)
        for lane_id in signs:
            lane = ET.SubElement(bank, 'lane', {'id': str(lane_id), 'type': 'driving', 'level': 'false'})
            ET.SubElement(lane, 'link')
            ET.SubElement(lane, 'width', {'sOffset': '0', 'a': '3.5', 'b': '0', 'c': '0', 'd': '0'})
            ET.SubElement(lane, 'roadMark', {'sOffset': '0', 'type': 'broken', 'weight': 'standard',
                                           'color': 'white', 'width': '.12', 'laneChange': 'both'})
    centre = ET.SubElement(section, 'center')
    lane = ET.SubElement(centre, 'lane', {'id': '0', 'type': 'none', 'level': 'false'})
    ET.SubElement(lane, 'roadMark', {'sOffset': '0', 'type': 'solid', 'weight': 'standard',
                                    'color': 'yellow', 'width': '.12', 'laneChange': 'none'})
    path.write_text(ET.tostring(root, encoding='unicode') + '\n')


def stop_scene(path):
    root = ET.parse(PILOT / 'intersection.xodr').getroot()
    approach = root.find('road[@id="1"]')
    signals = ET.SubElement(approach, 'signals')
    ET.SubElement(signals, 'signal', {'id': '1', 'name': 'near_side_stop_sign',
        's': '62', 't': '-5', 'zOffset': '0', 'hOffset': '0', 'roll': '0', 'pitch': '0',
        'orientation': '+', 'dynamic': 'no', 'country': 'OpenDRIVE', 'type': '206',
        'subtype': '0', 'value': '0', 'height': '2.1', 'width': '.6'})
    objects = ET.SubElement(approach, 'objects')
    ET.SubElement(objects, 'object', {'id': '2', 'name': 'near_side_crosswalk',
        'type': 'crosswalk', 's': '68', 't': '0', 'zOffset': '0', 'hdg': '0',
        'length': '3', 'width': '14', 'height': '.01'})
    path.write_text(ET.tostring(root, encoding='unicode') + '\n')


MODES = {
    'NRS-484B-400-2b': ('left_turn', 'exit_right_offset_m', [(1.75, 'right_exit'), (-1.75, 'left_exit')], 'm'),
    'NRS-484B-253': ('yield_turn', 'yield_wait_s', [(1., 'yield_wait'), (0., 'no_wait')], 's'),
    'NRS-484B-223-1b': ('lane_change', 'signal_lead_m', [(15., 'signal_before'), (0., 'signal_at_move')], 'm'),
    'NRS-484B-127-3': ('following', 'commanded_gap_m', [(15., 'gap_15'), (30., 'gap_30')], 'm'),
    'NRS-484A-450-2': ('stop', 'stop_duration_s', [(1., 'one_second_stop'), (0., 'no_stop')], 's'),
}

METHODS = {
    'drv.turning': 'original world pose and heading bracket the actual turn',
    'drv.in_intersection': 'native junction box joined to full original actor body',
    'st.centre_line': 'authored center road mark and native lane geometry',
    'rel.occupies': 'full original actor body versus native roadway polygon',
    'kin.position': 'original actor world XYZ each tick',
    'kin.heading': 'original actor yaw each tick',
    'kin.speed': 'original actor velocity norm each tick',
    'st.lane_direction': 'native map lane signed ID and topology',
    'st.lane_enters': 'native incoming road links and lane projection',
    'sig.turn_indicator': 'original VehicleLightState sampled before lateral movement',
    'rel.oncoming': 'opposing native actor pose and heading in the same frame',
    'drv.approaching': 'original actor position and speed toward junction',
    'drv.time_to_conflict': 'original subject/opposing position and velocity projection',
    'drv.yields_to': 'original subject stationary interval relative to opposing passage',
    'drv.arrival_order': 'original crossing-time brackets for both actors',
    'drv.laned_roadway': 'native two-lane same-direction map inventory',
    'st.lane': 'native lane IDs, widths, markings and projections',
    'drv.lane_change': 'original lateral body trajectory across native lane divider',
    'drv.distance_while': 'integrated original path distance during signal interval',
    'drv.lane_change_feasible': 'original target-lane actor body gap and time to conflict',
    'rel.surface_gap': 'same-frame original actor body vertices and nearest separation',
    'drv.following': 'same-frame subject/leader pose, direction and gap history',
    'drv.queue_behind': 'same-direction ordered actor body footprints',
    'rel.same_direction': 'native heading difference and lane directions',
    'ru.trailer_or_combination': 'native actor and attachment inventory; absence retained as unknown until checked',
    'dev.stop_sign': 'native sign landmark identity, authored asset and original rendered view',
    'dev.governs': 'native sign placement and incoming lane topology',
    'st.crosswalk': 'near-side native crosswalk geometry and visible rendering',
    'st.stop_line': 'native line inventory and original rendered view',
    'st.intersection': 'native junction geometry and actor body overlap',
    'st.sight_distance': 'original any-body ray/obstruction samples, not a named weather setting',
    'rel.visible': 'same-frame target body rays and retained obstruction status',
    'drv.stopped': 'original speed and body position stationary interval',
    'drv.crossing_line': 'full original body front crossing native line geometry',
    'drv.entering_intersection': 'original body/junction boundary entry bracket',
}


def make_fixture(folder, mode):
    source = REPO / 'work/_shared/fixtures/base-v3'
    target = folder / 'fixture-diagnostic'
    if not target.exists():
        shutil.copytree(source, target)
    trace = [json.loads(s) for s in (target / 'trace.jsonl').read_text().splitlines()]
    evidence = [json.loads(s) for s in (target / 'capture/evidence.jsonl').read_text().splitlines()]
    channels = target / 'channels'
    channels.mkdir(exist_ok=True)
    write(target / 'native-controls.json', {'landmarks': [], 'crosswalk_vertices_m': [],
        'native_object_names': [], 'actor_inventory': [],
        'scope': 'diagnostic retained straight-road source has no assigned stop/sign/crosswalk inventory'})
    values = {'kin.position': [], 'kin.heading': [], 'kin.speed': [], 'source_observations': []}
    for point, event in zip(trace, evidence):
        if point['frame'] != event['original_frame']:
            raise ValueError('Retained diagnostic frame mismatch')
        values['kin.position'].append(point['position_m'])
        values['kin.heading'].append(point['heading_deg'])
        values['kin.speed'].append(point['speed_mps'])
        values['source_observations'].append({'mode': mode, 'route_index': None,
            'ego_body_vertices_m': event['ego']['body_vertices_m'], 'other': None,
            'native_light_state': None, 'road_projection': event['world']['road_projection'],
            'native_observations': event['original_observations'],
            'native_topology_reference': None, 'applied_control': point['control'],
            'native_controls_reference': 'native-controls.json',
            'scenario_motion_completed': False})
    for name, items in values.items():
        with (channels / (name + '.jsonl')).open('w') as stream:
            for point, value in zip(trace, items):
                stream.write(json.dumps({'time_s': point['time_s'], 'value': value}) + '\n')
    provenance = json.loads((target / 'fixture-provenance.json').read_text())
    provenance['partition01_adaptation'] = [
        'Pinned retained three-frame straight-road source; no assigned maneuver or device was observed.',
        'All diagnostic channels were generated before analysis from retained trace/evidence.',
        'Other-actor, sign, crossing, signal and route-completion fields are explicitly unknown/absent.',
        'Software compatibility only; no physical success or statutory judgment.']
    (target / 'fixture-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


def build(folder):
    aid = folder.name
    folder.mkdir(parents=True, exist_ok=True)
    assignment_path = REPO / 'inputs' / aid / 'assignment.json'
    assignment = json.loads(assignment_path.read_text())
    mode, variable, settings, unit = MODES[assignment['law_id']]
    for sub in ('tests', 'proposals', 'constructions'):
        (folder / sub).mkdir(exist_ok=True)
    if folder != BASE:
        shutil.copyfile(BASE / 'runner.py', folder / 'runner.py')
        shutil.copyfile(BASE / 'analyze.py', folder / 'analyze.py')
        shutil.copyfile(BASE / 'tests/test_scenario.py', folder / 'tests/test_scenario.py')
    if mode in ('left_turn', 'yield_turn'):
        shutil.copyfile(PILOT / 'intersection.xodr', folder / 'scene.xodr')
    elif mode == 'stop':
        stop_scene(folder / 'scene.xodr')
    else:
        straight_scene(folder / 'scene.xodr')
    make_fixture(folder, mode)
    description = {'channels': [{'name': name, 'unit': units, 'sampling_rate_hz': 20,
        'method': method, 'time_window': 'all original recorded ticks',
        'reference_frame': 'CARLA world / native OpenDRIVE',
        'uncertainty': 'finite source sampling; legal/physical predicate remains for native measurement'}
        for name, units, method in [
            ('kin.position','structured','original actor world XYZ'),
            ('kin.heading','deg','original actor world yaw'),
            ('kin.speed','m/s','original actor velocity norm'),
            ('source_observations','structured','same-frame original actors, body vertices, map and controls')]],
        'context_inputs':[], 'limitations':['Three-frame software fixture does not demonstrate the assigned maneuver or device.']}
    cases = []
    for value, label in settings:
        assignments = {variable: {'value': value, 'unit': unit, 'kind': 'controller'}}
        if mode == 'left_turn':
            assignments['approach_lateral_m'] = {'value': 1.75, 'unit': 'm', 'kind': 'controller'}
        case = {'case_id': aid + '__' + label, 'target_law_id': assignment['law_id'],
            'target_type': 'boundary_probe', 'rationale': 'Freeze one physical control setting and measure original source contrasts; no legal cutoff or label is selected.',
            'variable_assignments': assignments,
            'unresolved_judgment_calls': [assignment['law']['text'], 'Public-way/device authority remains synthetic context.'],
            'recording_description': description}
        cases.append(case)
    write(folder / 'proposals/cases.json', {'status':'draft','cell_id':assignment['cell_id'],
                                           'actor':assignment['actor'],'sweep_specs':[],'cases':cases})
    terms = [x['term'] for x in assignment['source_observation_terms']]
    mapping = {}
    for term in terms:
        channel = term if term in ('kin.position','kin.heading','kin.speed') else 'source_observations'
        mapping[term] = {'evidence': METHODS.get(term, 'same-frame original native participant/road observation'),
                         'channels': [channel], 'source_refs': ['scene.xodr', 'capture/evidence.jsonl']}
    plan = {'assignment_id':aid,'actor':assignment['actor'],'cell_id':assignment['cell_id'],
        'law_id':assignment['law_id'],'cases':cases,
        'comparisons':[{'case_ids':[x['case_id'] for x in cases],
                        'deliberate_differences':[variable + ': ' + str(settings[0][0]) + ' vs ' + str(settings[1][0]) + ' ' + unit],
                        'fixed_conditions':['same authored geometry','same actor blueprints','same cameras and speed controller']}],
        'observations':[{'name':name,'mandatory':True,'description':method}
            for name,method in [('kin.position','original world position'),('kin.heading','original yaw'),
                                ('kin.speed','original velocity norm'),('source_observations','same-frame native actor/map evidence')]],
        'source_observation_mapping':mapping,
        'sources':[{'path':str(assignment_path.relative_to(REPO)),'sha256':sha(assignment_path)},
                   {'path':'runtime/main-pipeline-v1/SOURCE-MANIFEST.json','sha256':sha(RUNTIME/'SOURCE-MANIFEST.json')},
                   {'path':'skills/worker-preparation/SKILL.md','sha256':sha(REPO/'skills/worker-preparation/SKILL.md')},
                   {'path':str((folder/'scene.xodr').relative_to(REPO)),'sha256':sha(folder/'scene.xodr')}],
        'existing_evidence':assignment['existing_evidence'],
        'runtime_uncertainties':['actual scene/device existence and authority','physical controller outcome',
                                  'source actor/body geometry','camera visibility/duration','synthetic public-way context']}
    write(folder / 'case-plan.json', plan)
    base_config = {'actor':assignment['actor'],'law_id':assignment['law_id'],'cell_id':assignment['cell_id'],
        'mode':mode,'supported_case_ids':[c['case_id'] for c in cases],
        'required_atoms':['kin.position','kin.heading','kin.speed'],
        'authored_test_context':{'core_assumptions':[['asm.public_highway',True]],
            'public_highway_provenance':'Synthetic test assumption, not administrative proof',
            'caravan_membership': ['ego', 'other'] if mode=='following' else [],
            'district': 'other_area' if mode=='following' else None,
            'scenario':assignment['branch']},'public_way_road_ids':[],
        'target_speed_mps':5.,'max_ticks':500,
        'route_last_index': 132 if mode=='stop' else (300 if mode in ('following','lane_change') else 336),
        'cameras':[{'width':1920,'height':1080,'x':-8,'y':0,'z':35,'pitch':-80,'yaw':0},
                   {'width':1280,'height':720,'x':2,'y':0,'z':4,'pitch':-10,'yaw':0},
                   {'width':1280,'height':720,'x':-4,'y':-8,'z':5,'pitch':-12,'yaw':25},
                   {'width':1280,'height':720,'x':7,'y':-3,'z':8,'pitch':-35,'yaw':90}]}
    write(folder / 'config.json', dict(base_config, case=cases[0], selected_case_id=cases[0]['case_id']))
    common = ['runner.py','analyze.py','scene.xodr','tests/test_scenario.py']
    def construction(case):
        files=[{'path':name,'content':(folder/name).read_text(),
                'source':str((folder/name).relative_to(REPO))} for name in common]
        files.append({'path':'config.json','content':json.dumps(dict(base_config,case=case,selected_case_id=case['case_id']),indent=2)+'\n'})
        return {'case_id':case['case_id'],'cell_id':assignment['cell_id'],'actor':assignment['actor'],
            'entrypoint':'runner.py','recording_description':description,
            'measurement_plan':'Saved original source pose, body, actor/device and route measurements for '+mode,
            'static_checks':['OpenDRIVE lane structure','original frame/channel join','source camera decode'],
            'termination_rules':['source-measured route endpoint or maximum 500 original ticks'],
            'mechanisms':['native controller '+mode,'PipelineCapture original source','four RGB cameras'],
            'files':files}
    write(folder / 'construction.json', construction(cases[0]))
    entries=[]
    for case in cases:
        path=folder/'constructions'/(case['case_id']+'.json')
        write(path,construction(case))
        acquisition={name:{'entrypoint':'runner.py','method':'same-frame original actor/map acquisition and source-bound analysis',
                           'evidence':['trace.jsonl','capture/evidence.jsonl','channels/'+name+'.jsonl']}
                     for name in ('kin.position','kin.heading','kin.speed','source_observations')}
        entries.append({'case_id':case['case_id'],'kind':'capability',
            'construction':str(path.relative_to(folder)),'construction_sha256':sha(path),
            'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'partition01-capability-report-v1'},
            'acquisition':acquisition})
    write(folder/'execution-manifest.json',{'format':'worker-execution-manifest-v1','assignment_id':aid,
        'runtime_manifest_sha256':sha(RUNTIME/'SOURCE-MANIFEST.json'),'cases':entries})
    return mode,len(cases)


if __name__=='__main__':
    for aid in PARTITION:
        print(aid,build(REPO/'work'/aid))
