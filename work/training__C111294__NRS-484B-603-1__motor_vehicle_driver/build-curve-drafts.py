"""Construct same-cell curve alternatives with source-measured lane offset."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Missing or repeated curve anchor: ' + old[:60])
    return text.replace(old, new, 1)


def curve_road():
    root = ET.fromstring((HERE / 'native/authored-road.xodr').read_text())
    road = next(row for row in root.findall('road') if row.get('id') == '1')
    lanes = road.find('lanes')
    for row in list(lanes.findall('laneOffset')):
        lanes.remove(row)
    # Four zero-slope cubic joins: 0 -> 1.2 -> -1.2 -> 0 metres.
    for index, (station, start, end, length) in enumerate(((0, 0, 0, 100), (100, 0, 1.2, 45),
                                        (145, 1.2, -1.2, 45), (190, -1.2, 0, 43))):
        delta = end - start
        lanes.insert(index, ET.Element('laneOffset', {'s': str(station), 'a': str(start),
                            'b': '0', 'c': str(3 * delta / length**2),
                            'd': str(-2 * delta / length**3)}))
    return ET.tostring(root, encoding='unicode') + '\n'


def runner_source(text):
    text = once(text,
        'command = control_command(speed, transform.location.x - 1.75,\n                    transform.rotation.yaw + 90, target_mph(case, candidate, transform.location.y), plan["knobs"])',
        'ahead = mapping.get_waypoint(carla.Location(x=transform.location.x,\n                    y=transform.location.y - 10, z=.2), project_to_road=True,\n                    lane_type=carla.LaneType.Driving)\n                if ahead is None:\n                    raise RuntimeError("Original Native curve waypoint missing")\n                command = control_command(speed, transform.location.x - ahead.transform.location.x,\n                    transform.rotation.yaw - ahead.transform.rotation.yaw,\n                    target_mph(case, candidate, transform.location.y), plan["knobs"])')
    text = once(text, '"territorial_applicability_verified": False})',
        '"territorial_applicability_verified": False,\n'
        '            "curve_design": {"road_id": 1, "offset_stations_m": [100, 145, 190, 233],\n'
        '                "source_kind": "original Native road and route readback"}})')
    return text


def finalizer_source(text):
    marker = '\ndef finalize(folder: Path, contract: dict, expected_source_sha256: str) -> dict:\n'
    method = '''
def measure_curve_approach(folder: Path, value: dict) -> dict:
    import xml.etree.ElementTree as ET
    source = _rows(folder, "native_samples.jsonl")
    context = json.loads(_required(folder, "context.json").read_text())
    road = ET.fromstring(_required(folder, "road.xodr").read_text())
    first = next((r for r in road.findall("road") if r.get("id") == "1"), None)
    offsets = [] if first is None else first.findall("lanes/laneOffset")
    stations = {int(float(x.get("s", -1))) for x in offsets}
    if not context.get("curve_design") or not {100, 145, 190} <= stations or len(source) != 600:
        raise ValueError("Missing source-bound curve geometry")
    x = [row["ego_position_m"][0] for row in source]
    excursion = max(x) - min(x)
    if excursion < .6:
        raise ValueError("Original Native ego path did not traverse curve")
    return dict(value, measured_lateral_excursion_m=excursion,
                road_curve_stations_m=[100, 145, 190, 233],
                curve_necessity_legally_verified=False)

'''
    text = once(text, marker, '\n' + method + marker)
    text = once(text, 'value = measure_intersection_approach(rows, relation, road)',
                'value = measure_curve_approach(folder, measure_intersection_approach(rows, relation, road))')
    text = once(text,
        'req["output_key"] != "intersection_approach" or req["method"] != "measure_intersection_approach"',
        'req["output_key"] != "curve_approach" or req["method"] != "measure_curve_approach"')
    text = once(text, 'report["measurements"]["intersection_approach"]["value"]',
                'report["measurements"]["curve_approach"]["value"]')
    return text


def build(old, new, candidate='primary'):
    source = HERE / (f'current-v2-{old}-diagnostic/construction.json' if candidate == 'primary'
                     else f'current-v2-{old}-fallback1-diagnostic/construction.json')
    construction = json.loads(source.read_text())
    construction['case_id'] = construction['case_id'].replace(old, new)
    road = curve_road()
    original_hash = sha((HERE / 'native/authored-road.xodr').read_text())
    for entry in construction['files']:
        path = entry['path']
        content = entry['content'].replace(old, new)
        if path == 'authored-road.xodr':
            content = road
            entry.pop('source', None)
        elif path == 'geometry.py':
            content = once(content, original_hash, sha(road))
            entry.pop('source', None)
        elif path == 'runner.py':
            content = runner_source(content)
        elif path == 'finalize.py':
            content = finalizer_source(content)
        elif path == 'measurement-contract.json':
            data = json.loads(content)
            data['requirements'][0].update(disposition_index=1,
                output_key='curve_approach', method='measure_curve_approach',
                inputs=['native_samples.jsonl', 'road.xodr', 'context.json'])
            content = json.dumps(data, indent=2) + '\n'
        elif path == 'config.json':
            data = json.loads(content)
            data['supported_case_ids'] = [HERE.name + '__' + new]
            data['recording_description']['context_inputs'].append({
                'name': 'curve_design', 'unit': 'structured',
                'method': 'original Native lane offset and ego lateral path readback'})
            content = json.dumps(data, indent=2) + '\n'
            construction['recording_description'] = data['recording_description']
        entry['content'] = content
    suffix = new if candidate == 'primary' else new + '-fallback1'
    target = HERE / 'curve-branch-drafts' / suffix
    target.mkdir(parents=True, exist_ok=True)
    (target / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    for entry in construction['files']:
        if entry.get('source'):
            continue
        path = target / entry['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry['content'])
    return target


if __name__ == '__main__':
    for old, new in (('probe_a', 'curve_probe_a'), ('probe_b', 'curve_probe_b')):
        print(build(old, new))
        print(build(old, new, 'fallback1'))
