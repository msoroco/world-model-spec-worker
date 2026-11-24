"""Independent CPU audit of the two authored, unselected route requests."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from roundabout_direction import read_and_measure

BASE = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve().parent
PREFIX = BASE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    road = SOURCE / 'roundabout-road.xodr'
    original = (BASE.parent /
        'training__C132497__LVMC-11-43-010-C2__motor_vehicle_driver' /
        'right-exit-road.xodr')
    if sha(road) != sha(original):
        raise ValueError('Copied authored OpenDRIVE source changed')
    document = ET.parse(road).getroot()
    roads = {int(node.attrib['id']): node for node in document.findall('road')}
    if set(roads) != {20, 21, 22, 23}:
        raise ValueError('Connected roundabout roads missing')
    for road_id, expected_curvature in ((21, 1 / 15), (23, 1 / 15)):
        geom = roads[road_id].find('./planView/geometry')
        arc = geom.find('arc')
        if arc is None or not math.isclose(float(arc.attrib['curvature']), expected_curvature):
            raise ValueError('Circulatory road curvature changed')
    if {int(j.attrib['id']) for j in document.findall('junction')} != {100, 101}:
        raise ValueError('Roundabout junction source changed')
    measured = {}
    for suffix, expected in (('probe_a', 'counterclockwise'), ('probe_b', 'clockwise')):
        path = BASE / 'draft-native' / suffix / 'construction.json'
        construction = json.loads(path.read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        if (config['roundabout_source_sha256'] != sha(road)
                or files['roundabout-road.xodr'] != road.read_text()
                or construction['case_id'] != PREFIX + '__' + suffix
                or config['requested_direction'] != expected):
            raise ValueError('Exact construction/source binding differs')
        fixture = SOURCE / ('audit-track-' + suffix + '.jsonl')
        fixture.write_text(files['requested-track.jsonl'])
        try:
            meter = read_and_measure(fixture, 'authored_native_request')
        finally:
            fixture.unlink()
        if (meter['translational_direction'] != expected or
                meter['within_frames'] != 600 or
                meter['source_frames'] != 600 or
                meter['original_native_observed'] is not False):
            raise ValueError('Authored translational direction differs')
        measured[suffix] = {'construction_sha256': sha(path),
                            'translational_direction': meter['translational_direction'],
                            'signed_radial_cross_sum_m2': meter['signed_radial_cross_sum_m2']}
    if measured['probe_a']['signed_radial_cross_sum_m2'] <= 0 or measured['probe_b']['signed_radial_cross_sum_m2'] >= 0:
        raise ValueError('Controlled contrast has no opposite translation')
    return {'format': 'c238396-authored-request-comparison-v1',
            'road_sha256': sha(road), 'probes': measured,
            'fixed_conditions': ['same road source', 'same radii', 'same 20 Hz window',
                                 'same cameras', 'same other vehicle path'],
            'deliberate_difference': 'ego translational direction',
            'original_native_observed': False, 'physical_completion': False,
            'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
