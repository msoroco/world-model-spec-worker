"""Exercise connected 287(c) OpenDRIVE source and negative topology controls."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from topology import inspect

HERE = Path(__file__).resolve().parent


def require_rejection(root, expected):
    try:
        inspect(ET.tostring(root, encoding='unicode'))
    except ValueError as exc:
        if expected not in str(exc):
            raise
    else:
        raise AssertionError('Disconnected OpenDRIVE topology was accepted')


def main():
    rows = []
    for label in ('marked', 'unmarked'):
        construction = json.loads((HERE / label / 'construction.json').read_text())
        road = next(item['content'] for item in construction['files'] if item['path'] == 'road.xodr')
        result = inspect(road)
        if not result['through_road_connected'] or result['lane_links_checked'] != 8:
            raise AssertionError('Through road check did not run')
        root = ET.fromstring(road)
        broken = root.find(".//road[@id='8']/planView/geometry")
        broken.set('y', '-32.5')
        require_rejection(root, 'Connector endpoints are disconnected')
        root = ET.fromstring(road)
        broken = root.find(".//road[@id='8']//lane[@id='-1']/link/successor")
        broken.set('id', '1')
        require_rejection(root, 'Connector lane link differs')
        rows.append({'case_id': construction['case_id'],
                     'road_sha256': hashlib.sha256(road.encode()).hexdigest(),
                     'through_road_connected': True, 'rejected_disconnected_geometry': True,
                     'rejected_wrong_lane_link': True, 'native_loaded': False})
    result = {'format': 'c230222-287c-authored-topology-cpu-proof-v1', 'cases': rows}
    target = HERE / 'topology-proof.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(rows), 'proof_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
