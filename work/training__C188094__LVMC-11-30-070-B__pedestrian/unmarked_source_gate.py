"""Fail closed on an unmarked crossing without sourced intersection geometry."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def validate(context, xodr_bytes, source_files):
    if context.get('native_map_sha256') != hashlib.sha256(xodr_bytes).hexdigest():
        raise ValueError('Original Native map hash differs')
    root = ET.fromstring(xodr_bytes)
    junctions = {item.get('id'): item for item in root.findall('junction')}
    roads = {item.get('id') for item in root.findall('road')}
    unmarked = [item for item in context.get('crosswalks', []) if item.get('kind') == 'unmarked']
    if not unmarked:
        raise ValueError('Unmarked crossing inventory absent')
    inventory = context.get('intersection_inventory', [])
    for crossing in unmarked:
        crossing_id = crossing.get('id')
        matches = [item for item in inventory if item.get('unmarked_crosswalk_id') == crossing_id]
        if len(matches) != 1:
            raise ValueError('Unmarked crossing/intersection source join absent')
        item = matches[0]
        junction = junctions.get(str(item.get('native_junction_id')))
        if junction is None:
            raise ValueError('Unmarked crossing has no Native junction')
        inbound = str(item.get('incoming_road_id'))
        connecting = str(item.get('connecting_road_id'))
        if inbound not in roads or connecting not in roads or not any(
                link.get('incomingRoad') == inbound and link.get('connectingRoad') == connecting
                for link in junction.findall('connection')):
            raise ValueError('Unmarked crossing lacks connected Native roads')
        source_path = item.get('sidewalk_edge_source_path')
        expected = item.get('sidewalk_edge_source_sha256')
        if not isinstance(source_path, str) or not isinstance(expected, str) or len(expected) != 64:
            raise ValueError('Unmarked crossing sidewalk source absent')
        content = source_files.get(source_path)
        if not isinstance(content, bytes) or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError('Unmarked crossing sidewalk source hash differs')
        bounds = crossing.get('bounds_m')
        if not isinstance(bounds, dict) or not all(k in bounds for k in ('min_x', 'max_x', 'min_y', 'max_y')):
            raise ValueError('Unmarked crossing body bounds absent')
    return {'format': 'c188094-unmarked-original-source-gate',
            'unmarked_crossing_count': len(unmarked),
            'joined_junction_count': len({m['native_junction_id'] for m in inventory if m.get('unmarked_crosswalk_id')}),
            'legal_status': 'independent_source_review_pending'}


def proof():
    xodr = (b'<OpenDRIVE><road id="1"/><road id="2"/><junction id="7">'
            b'<connection incomingRoad="1" connectingRoad="2"/></junction></OpenDRIVE>')
    sidewalk = b'{"source_kind":"native_sidewalk_edge_readback","edges":[]}'
    context = {'native_map_sha256': hashlib.sha256(xodr).hexdigest(),
               'crosswalks': [{'id': 'u1', 'kind': 'unmarked',
                               'bounds_m': {'min_x': 20, 'max_x': 22, 'min_y': -3, 'max_y': 3}}],
               'intersection_inventory': [{'unmarked_crosswalk_id': 'u1', 'native_junction_id': 7,
                                           'incoming_road_id': 1, 'connecting_road_id': 2,
                                           'sidewalk_edge_source_path': 'sidewalk-edges.json',
                                           'sidewalk_edge_source_sha256': hashlib.sha256(sidewalk).hexdigest()}]}
    positive = validate(context, xodr, {'sidewalk-edges.json': sidewalk})
    rejected = []
    for label, mutate in (
            ('missing_junction', lambda c: c['intersection_inventory'][0].update(native_junction_id=8)),
            ('missing_sidewalk_source', lambda c: c['intersection_inventory'][0].pop('sidewalk_edge_source_sha256')),
            ('missing_crossing_join', lambda c: c['crosswalks'][0].update(id='u2'))):
        altered = json.loads(json.dumps(context))
        mutate(altered)
        try:
            validate(altered, xodr, {'sidewalk-edges.json': sidewalk})
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError('Accepted invalid unmarked source: ' + label)
    try:
        validate(context, xodr, {'sidewalk-edges.json': sidewalk + b' '})
    except ValueError as error:
        if 'hash differs' not in str(error):
            raise
        rejected.append('tampered_sidewalk_source')
    else:
        raise AssertionError('Tampered sidewalk source accepted')
    return {'format': 'c188094-unmarked-source-gate-cpu-proof', 'passed': True,
            'positive': positive, 'rejected': rejected,
            'current_native_intersection_constructed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    output = Path(__file__).with_name('unmarked-source-proof.json')
    output.write_text(json.dumps(proof(), indent=2) + '\n')
    print(output.read_text())
