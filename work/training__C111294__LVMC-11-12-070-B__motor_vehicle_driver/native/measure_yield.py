"""Source-only 600-frame diagnostic for the entering-vehicle sequence.

Engineering speed tolerances classify the diagnostic motion; they are not legal cutoffs.
"""
from pathlib import Path
import hashlib
import json
import math
import xml.etree.ElementTree as ET

FRAMES = 600
RATE_HZ = 20
ASSIGNMENT = 'training__C111294__LVMC-11-12-070-B__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(root, expected_case):
    root = Path(root)
    for name in ('road.xodr', 'native_samples.jsonl'):
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    manifest_path = root / 'diagnostic-source-manifest.json'
    if not manifest_path.is_file() and (root / 'source-manifest.json').is_file():
        manifest_path = root / 'source-manifest.json'
    if not manifest_path.is_file():
        raise ValueError('Missing required source: diagnostic-source-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    source_kind = manifest.get('source_kind')
    if manifest.get('case_id') != expected_case or source_kind not in ('synthetic_native_sample', 'native_observation'):
        raise ValueError('Diagnostic source identity differs')
    for name in ('road.xodr', 'native_samples.jsonl'):
        if manifest.get('sha256', {}).get(name) != sha(root / name):
            raise ValueError('Saved source hash differs: ' + name)
    tree = ET.parse(root / 'road.xodr')
    road_ids = {int(road.attrib['id']) for road in tree.findall('road')}
    links = {(item.attrib['incomingRoad'], item.attrib['connectingRoad'])
             for item in tree.findall('junction/connection')}
    if road_ids != {1, 2, 3, 4, 13, 14} or not {('1', '13'), ('3', '14')} <= links:
        raise ValueError('Through/entering intersection geometry differs')
    rows = [json.loads(line) for line in (root / 'native_samples.jsonl').read_text().splitlines()]
    if len(rows) != FRAMES:
        raise ValueError('Full 600-frame source window absent')
    stopped = []
    about = []
    entrant_in = []
    through_approach = []
    through_hold = []
    early_through_entry = []
    first_native_frame = rows[0].get('native_frame')
    first_time = rows[0].get('time_s')
    if type(first_native_frame) is not int or not isinstance(first_time, (int, float)):
        raise ValueError('Original frame join differs')
    for index, row in enumerate(rows):
        if row.get('video_frame') != index or row.get('native_frame') != first_native_frame + index \
                or row.get('source_kind') != source_kind:
            raise ValueError('Original frame join differs')
        if not math.isclose(row.get('time_s', -1), first_time + index / RATE_HZ, abs_tol=1e-3):
            raise ValueError('Original time join differs')
        ego, entrant = row.get('through'), row.get('entrant')
        if not isinstance(ego, dict) or not isinstance(entrant, dict):
            raise ValueError('Two participant histories required')
        expected_through_road = 4 if ego.get('y_m', -math.inf) > 7 else (13 if ego.get('y_m', -math.inf) >= -7 else 1)
        expected_entrant_road = 3 if entrant.get('x_m', math.inf) < -7 else (14 if entrant.get('x_m', math.inf) <= 7 else 2)
        if (ego.get('road_id') != expected_through_road or entrant.get('road_id') != expected_entrant_road
                or ego.get('lane_id') != 1 or entrant.get('lane_id') != -1
                or not math.isclose(ego.get('x_m', math.inf), -1.75, abs_tol=.25)
                or not math.isclose(entrant.get('y_m', math.inf), -1.75, abs_tol=.25)):
            raise ValueError('Native road/lane roles differ')
        if any(not isinstance(actor.get(key), (int, float)) or not math.isfinite(actor[key])
               for actor in (ego, entrant) for key in ('x_m', 'y_m', 'speed_mps')):
            raise ValueError('Finite participant pose/speed absent')
        if ego['speed_mps'] < 0 or entrant['speed_mps'] < 0:
            raise ValueError('Negative speed source')
        if entrant['x_m'] < -7 and entrant['speed_mps'] <= .2:
            stopped.append(index)
        if -12 <= entrant['x_m'] <= -7 and entrant['speed_mps'] >= .5:
            about.append(index)
        if -7 <= entrant['x_m'] <= 7:
            entrant_in.append(index)
            if ego['y_m'] >= 7 and ego['speed_mps'] <= .3:
                through_hold.append(index)
        if 7 <= ego['y_m'] <= 30 and ego['speed_mps'] >= .5:
            through_approach.append(index)
        if about and entrant['x_m'] < 7 and ego['y_m'] < 7:
            early_through_entry.append(index)
    if len(stopped) < 40 or not about or min(about) <= max(stopped[:40]):
        raise ValueError('Entrant prior yield and about-to-enter sequence absent')
    if not entrant_in or not through_approach:
        raise ValueError('Crossing entrant or through approach absent')
    return {'format': 'c111294-yield-sequence-diagnostic-v1', 'case_id': expected_case,
            'frames': FRAMES, 'rate_hz': RATE_HZ, 'source_kind': source_kind,
            'road_sha256': sha(root / 'road.xodr'),
            'native_samples_sha256': sha(root / 'native_samples.jsonl'),
            'entrant_prior_stopped_frames': len(stopped), 'about_to_enter_first_frame': min(about),
            'through_approach_frames': len(through_approach),
            'through_hold_during_entrant_frames': len(through_hold),
            'through_entered_before_entrant_clear': bool(early_through_entry),
            'through_yield_response_observed': bool(through_hold) and not early_through_entry,
            'through_highway_designation_physically_verified': False,
            'entrant_lawful_prior_yield_verified': False,
            'legal_verdict': None, 'physical_observation_claimed': False}
