"""Audit the 287(c) authored midblock source pair and its proof limits."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    manifest = json.loads((HERE / 'manifest.json').read_text())
    require(manifest['assignment_id'] == ASSIGNMENT.name and len(manifest['cases']) == 2,
            '287(c) source pair identity differs')
    rows = []
    base_road = None
    for label, entry in zip(('marked', 'unmarked'), manifest['cases']):
        case = ASSIGNMENT.name + '__crossref_287c_' + label
        require(entry['case_id'] == case and not entry['candidates'], '287(c) case differs')
        path = HERE / entry['construction']
        require(sha(path) == entry['construction_sha256'], '287(c) construction changed')
        construction = json.loads(path.read_text())
        contract = json.loads((HERE / label / 'measurement-contract.json').read_text())
        recipe = json.loads((HERE / label / 'recipe.json').read_text())
        context_path = HERE / label / 'sources/curb-context.json'
        context = json.loads(context_path.read_text())
        require(contract['case_id'] == case and len(contract['requirements']) == 1 and
                contract['requirements'][0]['method'] == 'curb_departure',
                'Case-specific measurement contract differs')
        context_source = next((x for x in recipe['sources'] if x['path'] == 'curb-context.json'), None)
        require(context_source is not None and context_source['sha256'] == sha(context_path),
                'Case-specific fixture context is unbound')
        capture_manifest_path = HERE / label / 'sources/capture/manifest.json'
        capture_manifest = json.loads(capture_manifest_path.read_text())
        capture_source = next((x for x in recipe['sources'] if x['path'] == 'capture/manifest.json'), None)
        require(capture_source is not None and capture_source['sha256'] == sha(capture_manifest_path) and
                capture_manifest['sources']['road.xodr'] == context['authored_road_sha256'],
                'Case-specific capture road hash differs')
        require(construction['case_id'] == case and construction['cell_id'] == 'C230222' and
                construction['actor'] == 'pedestrian' and
                construction['law_id'] == 'NRS-484B-283-1b', 'Frozen cell differs')
        files = {f['path']: f['content'] for f in construction['files']}
        require(context['authored_road_sha256'] == hashlib.sha256(files['road.xodr'].encode()).hexdigest() and
                context['authored_adjacent_intersection_targets'] == 2 and
                context['authored_dynamic_device_targets'] == 2 and
                context['authored_marked_crossing_target'] == (label == 'marked'),
                'Synthetic source context does not match authored road')
        road = ET.fromstring(files['road.xodr'])
        main = road.find('road')
        require(len(road.findall('road')) == 7 and len(road.findall('junction')) == 2,
                'Two adjacent intersection targets required')
        road_by_id = {x.get('id'): x for x in road.findall('road')}
        for number in (1, 2):
            west, connector, east = (str(3 * number - 1), str(3 * number),
                                     str(3 * number + 1))
            junction = next(x for x in road.findall('junction') if x.get('id') == str(number))
            connections = junction.findall('connection')
            require({(x.get('incomingRoad'), x.get('connectingRoad'), x.get('contactPoint'))
                     for x in connections} == {(west, connector, 'start'),
                                                (east, connector, 'end')} and
                    {tuple(sorted(link.attrib.items())) for x in connections
                     for link in x.findall('laneLink')} ==
                    {tuple(sorted({'from': lane, 'to': lane}.items()))
                     for lane in ('-1', '1')},
                    'Adjacent junction connection or lane links differ')
            require(road_by_id[connector].get('junction') == str(number) and
                    road_by_id[west].find('link/successor').get('elementId') == str(number) and
                    road_by_id[east].find('link/predecessor').get('elementId') == str(number),
                    'Adjacent crossroad approach topology differs')
        require(main.get('length') == '80' and
                main.find('planView/geometry').get('y') == '-40',
                'Midblock curb crossing road differs')
        signals = main.findall('signals/signal')
        require({x.get('id') for x in signals} == {'28701', '28702'} and
                {x.get('s') for x in signals} == {'10', '70'} and
                all(x.get('dynamic') == 'yes' for x in signals),
                'Operating-device targets absent')
        marks = main.findall('objects/object')
        require(len(marks) == (1 if label == 'marked' else 0) and
                all(x.get('type') == 'crosswalk' and x.get('s') == '40' for x in marks),
                'Only the midblock marked-crossing variable may change')
        require('resolve_device_targets(world.get_actors())' in files['runner.py'] and
                'sample_device_targets(device_targets)' in files['runner.py'] and
                "'official_device_operation_verified': False" in files['runner.py'] and
                "'native_road_source': 'native-road.xodr'" in files['runner.py'],
                'Native actor readback and map capture must be source bound')
        signal_source = files['signal_control.py']
        require('get_opendrive_id' in signal_source and 'get_state' in signal_source and
                'Both adjacent-intersection Native devices required' in signal_source,
                'Device source cannot prove operation from authored IDs alone')
        road_without_objects = ET.fromstring(files['road.xodr'])
        road_without_objects.find('road/objects').clear()
        comparable = ET.tostring(road_without_objects)
        if base_road is None:
            base_road = comparable
        else:
            require(base_road == comparable, '287(c) pair changed more than crossing marking')
        offline = HERE / label / 'proofs/offline.log'
        require(offline.is_file() and '"offline_passed": true' in offline.read_text().lower(),
                'Pinned offline proof absent')
        rows.append({'case_id': case, 'construction_sha256': sha(path),
                     'authored_road_sha256': hashlib.sha256(files['road.xodr'].encode()).hexdigest(),
                     'measurement_contract_sha256': sha(HERE / label / 'measurement-contract.json'),
                     'fixture_recipe_sha256': sha(HERE / label / 'recipe.json'),
                     'synthetic_curb_context_sha256': sha(context_path),
                     'synthetic_capture_manifest_sha256': sha(capture_manifest_path),
                     'offline_log': str(offline.relative_to(HERE)),
                     'offline_log_sha256': sha(offline),
                     'marked_crossing_target': label == 'marked'})
    result = {'format': 'c230222-287c-authored-source-review-v1',
              'cases': rows, 'comparison_variable': 'marked_crossing_target',
              'frozen_cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'},
              'adjacent_intersection_targets': 2, 'requested_dynamic_device_targets': 2,
              'native_executed': False, 'device_actors_observed': False,
              'operating_official_devices_verified': False,
              'original_marking_pixels_verified': False,
              'legal_applicability_conclusion': None,
              'selected_for_delivery': False}
    target = HERE / 'source-proof.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'authored_source_pair': len(rows), 'source_proof_sha256': sha(target)}))


if __name__ == '__main__':
    main()
