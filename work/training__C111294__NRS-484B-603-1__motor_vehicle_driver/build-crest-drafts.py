"""Construct same-cell hill-crest alternatives with a continuous road elevation."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Missing or duplicate construction anchor: ' + old[:60])
    return text.replace(old, new, 1)


def crest_road():
    root = ET.fromstring((HERE / 'native/authored-road.xodr').read_text())
    road = next(r for r in root.findall('road') if r.attrib['id'] == '1')
    profile = road.find('elevationProfile')
    for child in list(profile):
        profile.remove(child)
    # Cubic smoothstep, z(0)=0, z(200)=2 m, z(233)=0; all joins have zero slope.
    ET.SubElement(profile, 'elevation', {'s': '0', 'a': '0', 'b': '0',
                                        'c': str(6 / 200**2), 'd': str(-4 / 200**3)})
    ET.SubElement(profile, 'elevation', {'s': '200', 'a': '2', 'b': '0',
                                        'c': str(-6 / 33**2), 'd': str(4 / 33**3)})
    return ET.tostring(root, encoding='unicode') + '\n'


def runner_source(text):
    text = once(text, 'carla.Location(x=1.75, y=120, z=.5), carla.Rotation(yaw=-90)',
        'carla.Location(x=1.75, y=120, z=mapping.get_waypoint(\n'
        '                carla.Location(x=1.75, y=120, z=.2), project_to_road=True).transform.location.z + .5),\n'
        '                carla.Rotation(yaw=-90)')
    text = once(text, '"territorial_applicability_verified": False})',
        '"territorial_applicability_verified": False,\n'
        '            "crest_design": {"road_id": 1, "peak_station_m": 200,\n'
        '                "authored_height_m": 2.0, "source_kind": "original Native map and ego-height readback"}})')
    return text


def finalizer_source(text):
    marker = '\ndef finalize(folder: Path, contract: dict, expected_source_sha256: str) -> dict:\n'
    method = '''
def measure_crest_approach(folder: Path, value: dict) -> dict:
    import xml.etree.ElementTree as ET
    source = _rows(folder, "native_samples.jsonl")
    context = json.loads(_required(folder, "context.json").read_text())
    road = ET.fromstring(_required(folder, "road.xodr").read_text())
    first = next((r for r in road.findall("road") if r.get("id") == "1"), None)
    grades = [] if first is None else first.findall("elevationProfile/elevation")
    if not context.get("crest_design") or len(grades) < 2 or len(source) != 600:
        raise ValueError("Missing source-bound hill crest geometry")
    if not any(float(g.get("s", -1)) == 200 for g in grades):
        raise ValueError("Hill crest station missing from Native map")
    heights = [r["ego_position_m"][2] for r in source]
    peak = max(range(20, 400), key=lambda i: heights[i])
    rise = heights[peak] - min(heights[:max(peak, 1)])
    fall = heights[peak] - min(heights[peak+1:500])
    if not 20 < peak < 400 or rise < .5 or fall < .5:
        raise ValueError("Original ego height does not traverse a hill crest")
    return dict(value, crest_peak_frame=peak, measured_ego_rise_m=rise,
                measured_ego_fall_m=fall, road_crest_station_m=200,
                crest_necessity_legally_verified=False)

'''
    text = once(text, marker, '\n' + method + marker)
    text = once(text, 'value = measure_intersection_approach(rows, relation, road)',
                'value = measure_crest_approach(folder, measure_intersection_approach(rows, relation, road))')
    text = once(text,
        'req["output_key"] != "intersection_approach" or req["method"] != "measure_intersection_approach"',
        'req["output_key"] != "crest_approach" or req["method"] != "measure_crest_approach"')
    text = once(text, 'report["measurements"]["intersection_approach"]["value"]',
                'report["measurements"]["crest_approach"]["value"]')
    return text


def build(old, new, candidate='primary'):
    source = HERE / (f'current-v2-{old}-diagnostic/construction.json' if candidate == 'primary'
                     else f'current-v2-{old}-fallback1-diagnostic/construction.json')
    construction = json.loads(source.read_text())
    construction['case_id'] = construction['case_id'].replace(old, new)
    road = crest_road()
    original = (HERE / 'native/authored-road.xodr').read_text()
    original_hash = sha(original)
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
            data['requirements'][0].update(disposition_index=2,
                output_key='crest_approach', method='measure_crest_approach',
                inputs=['native_samples.jsonl', 'road.xodr', 'context.json'])
            content = json.dumps(data, indent=2) + '\n'
        elif path == 'config.json':
            data = json.loads(content)
            data['supported_case_ids'] = [HERE.name + '__' + new]
            data['recording_description']['context_inputs'].append({
                'name': 'crest_design', 'unit': 'structured',
                'method': 'original Native map elevation and ego-height readback'})
            content = json.dumps(data, indent=2) + '\n'
            construction['recording_description'] = data['recording_description']
        entry['content'] = content
    suffix = new if candidate == 'primary' else new + '-fallback1'
    target = HERE / 'crest-branch-drafts' / suffix
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
    for old, new in (('probe_a', 'crest_probe_a'), ('probe_b', 'crest_probe_b')):
        print(build(old, new))
        print(build(old, new, 'fallback1'))
