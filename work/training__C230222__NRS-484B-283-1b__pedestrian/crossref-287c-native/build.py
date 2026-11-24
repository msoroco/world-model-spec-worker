"""Author a midblock 287(c) source pair without asserting Native operation."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
BASE = ASSIGNMENT.name
SOURCE = json.loads((ASSIGNMENT / 'v2-primary/probe_1/construction.json').read_text())
SOURCE_MANIFEST = json.loads((ASSIGNMENT / 'v2-primary-manifest.json').read_text())
SIGNALS = '''"""Bind requested official-device targets to actual Native actor readback."""
HEADS = {'south': '28701', 'north': '28702'}


def resolve(actors):
    found = {}
    for actor in actors:
        if not str(getattr(actor, 'type_id', '')).startswith('traffic.traffic_light'):
            continue
        getter = getattr(actor, 'get_opendrive_id', None)
        if getter is None:
            continue
        for role, signal_id in HEADS.items():
            if str(getter()) == signal_id:
                if role in found:
                    raise ValueError('Ambiguous Native device: ' + role)
                found[role] = actor
    if set(found) != set(HEADS) or found['south'].id == found['north'].id:
        raise ValueError('Both adjacent-intersection Native devices required')
    return found


def sample(heads):
    result = {}
    for role, actor in heads.items():
        state = str(actor.get_state()).split('.')[-1].lower()
        if state not in ('red', 'yellow', 'green'):
            raise ValueError('Native device is not in an operating phase: ' + role)
        result[role] = {'opendrive_id': HEADS[role], 'native_actor_id': actor.id,
                        'raw_state': state, 'source': 'native_readback',
                        'official_device_status_reviewed': False}
    return result
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def road(marked):
    root = ET.fromstring(next(x['content'] for x in SOURCE['files'] if x['path'] == 'road.xodr'))
    root.find('header').attrib.update({'north': '45', 'south': '-45',
                                       'east': '25', 'west': '-25'})
    main = root.find('road')
    main.set('name', 'C230222_midblock_between_adjacent_intersection_targets')
    main.set('length', '80')
    geom = main.find('planView/geometry')
    geom.set('y', '-40')
    geom.set('length', '80')
    main.find('objects').clear()
    if marked:
        ET.SubElement(main.find('objects'), 'object', {
            'id': '28703', 'name': 'midblock_marked_crosswalk_target',
            'type': 'crosswalk', 's': '40', 't': '0', 'zOffset': '0',
            'hdg': '-1.5707963267948966', 'length': '7', 'width': '3'})
    signals = main.find('signals')
    signals.clear()
    for role, sid, station in (('south', '28701', '10'), ('north', '28702', '70')):
        ET.SubElement(signals, 'signal', {
            'id': sid, 'name': 'C230222_287c_' + role + '_device_target',
            's': station, 't': '-4', 'zOffset': '3.5', 'hOffset': '0',
            'pitch': '0', 'roll': '0', 'orientation': '+', 'dynamic': 'yes',
            'country': 'US', 'type': '1000001', 'subtype': '0',
            'value': '0', 'unit': '', 'height': '0.6', 'width': '0.3'})
    for number, y in ((1, -30), (2, 30)):
        west_id, connector_id, east_id = (3 * number - 1, 3 * number, 3 * number + 1)
        for part, road_id, x, length, junction in (
            ('west_approach', west_id, -20, 16.5, '-1'),
            ('connector', connector_id, -3.5, 7, str(number)),
            ('east_approach', east_id, 3.5, 16.5, '-1'),
        ):
            cross = ET.fromstring(ET.tostring(main))
            cross.set('id', str(road_id))
            cross.set('name', 'adjacent_intersection_' + str(number) + '_' + part)
            cross.set('length', str(length))
            cross.set('junction', junction)
            crossgeom = cross.find('planView/geometry')
            crossgeom.set('x', str(x))
            crossgeom.set('y', str(y))
            crossgeom.set('hdg', '0')
            crossgeom.set('length', str(length))
            cross.find('objects').clear()
            cross.find('signals').clear()
            link = cross.find('link')
            link.clear()
            if part == 'west_approach':
                ET.SubElement(link, 'successor', {'elementType': 'junction',
                                                 'elementId': str(number)})
            elif part == 'connector':
                ET.SubElement(link, 'predecessor', {'elementType': 'road',
                                                   'elementId': str(west_id),
                                                   'contactPoint': 'end'})
                ET.SubElement(link, 'successor', {'elementType': 'road',
                                                 'elementId': str(east_id),
                                                 'contactPoint': 'start'})
                for lane_id in ('-1', '1'):
                    lane = cross.find(".//lane[@id='" + lane_id + "']")
                    lane_link = ET.SubElement(lane, 'link')
                    ET.SubElement(lane_link, 'predecessor', {'id': lane_id})
                    ET.SubElement(lane_link, 'successor', {'id': lane_id})
            else:
                ET.SubElement(link, 'predecessor', {'elementType': 'junction',
                                                   'elementId': str(number)})
            root.append(cross)
        junction = ET.SubElement(root, 'junction', {'id': str(number),
                                'name': 'adjacent_intersection_' + str(number) + '_target'})
        for connection_id, incoming, point, lane in (
            ('0', west_id, 'start', '-1'), ('1', east_id, 'end', '1')
        ):
            connection = ET.SubElement(junction, 'connection', {
                'id': connection_id, 'incomingRoad': str(incoming),
                'connectingRoad': str(connector_id), 'contactPoint': point})
            ET.SubElement(connection, 'laneLink', {'from': lane, 'to': lane})
    return ET.tostring(root, encoding='unicode') + '\n'


def geometry_source(marked):
    return '''"""CPU check of authored 287(c) targets; Native topology and operation remain unverified."""
from pathlib import Path
import xml.etree.ElementTree as ET


def check(path=Path(__file__).resolve().parent / 'road.xodr'):
    root = ET.parse(path).getroot()
    roads = root.findall('road')
    junctions = root.findall('junction')
    signals = root.findall('.//signals/signal')
    marks = [x for x in root.findall('.//objects/object') if x.get('type') == 'crosswalk']
    if len(roads) != 7 or len(junctions) != 2 or len(signals) != 2 or len(marks) != %d:
        raise ValueError('287(c) authored geometry or device targets differ')
    if any(len(j.findall('connection')) != 2 for j in junctions):
        raise ValueError('Adjacent junction lane connections differ')
    if {x.get('id') for x in signals} != {'28701', '28702'}:
        raise ValueError('Adjacent device identity differs')
    return {'authored_road_id': 1, 'length_m': 80, 'width_m': 7,
            'curb_edge_x_m': -3.5, 'vehicle_lane_center_x_m': -1.75,
            'vehicle_conflict_y_m': 0, 'adjacent_intersection_targets': 2,
            'device_targets': 2, 'marked_crosswalk_targets': %d,
            'authored_junction_connection_count': 4,
            'native_map_loaded': False, 'official_device_operation_verified': False,
            'legal_road_and_safety_place_status_verified': False}
''' % (int(marked), int(marked))


def build():
    entries = []
    for label, marked in (('marked', True), ('unmarked', False)):
        case = BASE + '__crossref_287c_' + label
        folder = HERE / label
        folder.mkdir(parents=True, exist_ok=True)
        construction = json.loads(json.dumps(SOURCE))
        construction['case_id'] = case
        files = {x['path']: x for x in construction['files']}
        config = json.loads(files['config.json']['content'])
        config['case_id'] = case
        config['selected_case_id'] = case
        config['case'] = {'case_id': case}
        config['case_suffix'] = 'crossref_287c_' + label
        config['supported_case_ids'] = [case]
        files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
        eng = files['engineering.py']['content']
        eng = eng.replace("('probe_1', 'probe_2')", "('crossref_287c_marked', 'crossref_287c_unmarked')")
        eng = eng.replace("start = .5 if suffix == 'probe_1' else 3.5", "start = .5")
        eng = eng.replace("'comparison_variable': 'pedestrian_departure_s'", "'comparison_variable': 'marked_crosswalk_target'")
        files['engineering.py']['content'] = eng
        runner = files['runner.py']['content']
        runner = runner.replace('from engineering import candidate',
            'from engineering import candidate\nfrom signal_control import resolve as resolve_device_targets, sample as sample_device_targets')
        runner = runner.replace('library = world.get_blueprint_library()',
            "library = world.get_blueprint_library()\n        device_targets = resolve_device_targets(world.get_actors())\n        for head in device_targets.values():\n            head.freeze(True)\n            head.set_state(carla.TrafficLightState.Green)")
        runner = runner.replace("'vehicle_brake_command_onset_s': policy.brake_command_onset_s}",
            "'vehicle_brake_command_onset_s': policy.brake_command_onset_s,\n                    'adjacent_device_readback': sample_device_targets(device_targets),\n                    'official_device_operation_verified': False}")
        files['runner.py']['content'] = runner
        files['road.xodr']['content'] = road(marked)
        files['geometry.py']['content'] = geometry_source(marked)
        files['signal_control.py'] = {'path': 'signal_control.py', 'content': SIGNALS}
        tests = '''import unittest
from geometry import check
from signal_control import resolve, sample


class FakeLight:
    type_id = 'traffic.traffic_light'

    def __init__(self, opendrive_id, actor_id, state):
        self.source = opendrive_id
        self.id = actor_id
        self.state = state

    def get_opendrive_id(self):
        return self.source

    def get_state(self):
        return self.state


class SourceTargets(unittest.TestCase):
    def test_road_and_device_targets(self):
        source = check()
        self.assertEqual(source['adjacent_intersection_targets'], 2)
        self.assertEqual(source['device_targets'], 2)
        self.assertFalse(source['official_device_operation_verified'])

    def test_missing_native_devices_reject(self):
        with self.assertRaisesRegex(ValueError, 'Both adjacent-intersection'):
            resolve([])

    def test_two_distinct_native_readbacks(self):
        heads = resolve([FakeLight('28701', 21, 'Green'),
                         FakeLight('28702', 22, 'Green')])
        rows = sample(heads)
        self.assertEqual({x['source'] for x in rows.values()}, {'native_readback'})
        self.assertFalse(any(x['official_device_status_reviewed'] for x in rows.values()))

    def test_nonoperating_native_state_rejected(self):
        heads = resolve([FakeLight('28701', 21, 'Off'),
                         FakeLight('28702', 22, 'Green')])
        with self.assertRaisesRegex(ValueError, 'not in an operating phase'):
            sample(heads)
'''
        files['tests/test_offline.py']['content'] = tests
        construction['files'] = list(files.values())
        path = folder / 'construction.json'
        path.write_text(json.dumps(construction, indent=2) + '\n')
        contract = json.loads((ASSIGNMENT / 'v2-primary/probe_1/measurement-contract.json').read_text())
        contract['case_id'] = case
        (folder / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
        recipe = json.loads((ASSIGNMENT / 'v2-primary/probe_1/recipe.json').read_text())
        context = json.loads((ASSIGNMENT / 'v2-primary/probe_1/sources/curb-context.json').read_text())
        context['authored_road_sha256'] = digest(files['road.xodr']['content'].encode())
        context['authored_adjacent_intersection_targets'] = 2
        context['authored_dynamic_device_targets'] = 2
        context['authored_marked_crossing_target'] = marked
        source_dir = folder / 'sources'
        source_dir.mkdir(exist_ok=True)
        context_path = source_dir / 'curb-context.json'
        context_path.write_text(json.dumps(context, indent=2) + '\n')
        capture_dir = source_dir / 'capture'
        capture_dir.mkdir(exist_ok=True)
        capture_manifest = json.loads((ASSIGNMENT / 'v2-primary/probe_1/sources/capture/manifest.json').read_text())
        capture_manifest['sources']['road.xodr'] = context['authored_road_sha256']
        capture_manifest_path = capture_dir / 'manifest.json'
        capture_manifest_path.write_text(json.dumps(capture_manifest, indent=2) + '\n')
        for row in recipe['sources']:
            if row['path'] == 'curb-context.json':
                row['source'] = 'work/' + BASE + '/crossref-287c-native/' + label + '/sources/curb-context.json'
                row['sha256'] = digest(context_path.read_bytes())
            if row['path'] == 'capture/manifest.json':
                row['source'] = 'work/' + BASE + '/crossref-287c-native/' + label + '/sources/capture/manifest.json'
                row['sha256'] = digest(capture_manifest_path.read_bytes())
        (folder / 'recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
        entry = json.loads(json.dumps(SOURCE_MANIFEST['cases'][0]))
        entry['case_id'] = case
        entry['construction'] = str(path.relative_to(HERE))
        entry['construction_sha256'] = digest(path.read_bytes())
        entry['measurement_contract'] = label + '/measurement-contract.json'
        entry['fixture_recipe'] = 'work/' + BASE + '/crossref-287c-native/' + label + '/recipe.json'
        entry['candidates'] = []
        entry['candidate_risk'] = {'status': 'none', 'reason': 'Initial CPU source feasibility only; physical fallback review remains pending'}
        entries.append(entry)
    manifest = dict(SOURCE_MANIFEST)
    manifest['cases'] = entries
    manifest['status'] = 'unselected_cpu_source_feasibility'
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    public = json.loads(json.dumps(manifest))
    for entry in public['cases']:
        entry['construction'] = 'crossref-287c-native/' + entry['construction']
        entry['measurement_contract'] = 'crossref-287c-native/' + entry['measurement_contract']
    (ASSIGNMENT / 'crossref-287c-manifest.json').write_text(json.dumps(public, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'marked': True, 'native_executed': False}))


if __name__ == '__main__':
    build()
