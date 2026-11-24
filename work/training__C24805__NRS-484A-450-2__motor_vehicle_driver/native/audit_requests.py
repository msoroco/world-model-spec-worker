"""Independent fixed-condition and source hierarchy audit of C24805 drafts."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from sight_stop import measure

BASE = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve().parent
PREFIX = BASE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    road = SOURCE / 'road.xodr'
    original = BASE.parent / 'training__C111325__NRS-484A-450-2__motor_vehicle_driver' / 'native/road.xodr'
    now = ET.parse(road).getroot()
    before = ET.parse(original).getroot()
    approach = next(r for r in now.findall('road') if r.get('id') == '1')
    previous = next(r for r in before.findall('road') if r.get('id') == '1')
    if ET.tostring(approach.find('planView')) != ET.tostring(previous.find('planView')):
        raise ValueError('Approach geometry changed')
    if ET.tostring(approach.find('signals')) != ET.tostring(previous.find('signals')):
        raise ValueError('Stop-sign source changed')
    if not any(o.get('type') == 'crosswalk' for o in previous.findall('objects/object')):
        raise ValueError('Original branch crosswalk source absent')
    if approach.findall('objects/object'):
        raise ValueError('Marked crosswalk/stop-line source remains')
    probes = {}
    other_paths = []
    for suffix, expected in (('probe_a', True), ('probe_b', False)):
        construction_path = BASE / 'draft-native' / suffix / 'construction.json'
        construction = json.loads(construction_path.read_text())
        files = {f['path']: f['content'] for f in construction['files']}
        config = json.loads(files['config.json'])
        if (construction['case_id'] != PREFIX + '__' + suffix
                or config['road_source_sha256'] != sha(road)
                or files['road.xodr'] != road.read_text()
                or config['requested_pre_entry_stop'] != expected):
            raise ValueError('Exact construction/source binding differs')
        rows = [json.loads(line) for line in files['requested-track.jsonl'].splitlines()]
        result = measure(rows, 'authored_native_request')
        if (result['diagnostic_full_halt_span'] != expected
                or result['original_native_observed'] is not False
                or result['view_point_nearest_intersecting_highway_verified'] is not False):
            raise ValueError('Stop request contrast or provenance differs')
        other_paths.append([row['other_vehicle_xy_m'] for row in rows])
        probes[suffix] = {'construction_sha256': sha(construction_path),
                          'stop_span_frames': result['longest_pre_entry_low_speed_frames'],
                          'intersection_entry_frame': result['entry_frame']}
    if other_paths[0] != other_paths[1]:
        raise ValueError('Other vehicle path differs')
    return {'format': 'c24805-no-reference-request-comparison-v1',
            'road_sha256': sha(road), 'probes': probes,
            'fixed_conditions': ['connected road centerline and lanes',
                                 'governing stop sign', 'other vehicle path',
                                 'four source cameras', '30-second 20 Hz window'],
            'deliberate_difference': 'requested ego stop versus rolling motion',
            'marked_references_absent_in_authored_road': True,
            'unmarked_crosswalk_absence_verified': False,
            'driver_view_nearest_point_verified': False,
            'original_native_observed': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
