"""Check source hashes, frame joins and distinct physical branch requests."""
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASES = ('device_controlled', 'opposing_no_turn', 'opposing_left_turn')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(suffix, altered=None):
    if suffix not in CASES:
        raise ValueError('Unknown branch case')
    root = HERE/suffix
    source = root/'sources'
    inventory = json.loads((root/'source-inventory.json').read_text())
    for name,digest in inventory['sources'].items():
        if sha(source/name) != digest:
            raise ValueError('Branch source hash changed: '+name)
    history = json.loads((Path(altered) if altered else source/'actor-history.json').read_text())
    rows = history['rows']
    maps = read_jsonl(source/'video_frames.jsonl')
    evidence = read_jsonl(source/'capture/evidence.jsonl')
    traces = read_jsonl(source/'trace.jsonl')
    if not all(len(x)==600 for x in (rows,maps,evidence,traces)):
        raise ValueError('Branch source frame count changed')
    for i,(row,mapped,ev,trace) in enumerate(zip(rows,maps,evidence,traces)):
        if (row['frame']!=i or mapped['video_frame']!=i or
                ev['original_frame']!=i or trace['frame']!=i or
                abs(row['time_s']-mapped['time_s'])>1e-9 or
                abs(row['time_s']-ev['recording_time_s'])>1e-9 or
                abs(row['time_s']-trace['time_s'])>1e-9 or
                row['other']['body_xyz_m']!=ev['other_actors'][0]['body_vertices_m'] or
                row['other']['center_xyz_m']!=ev['other_actors'][0]['position_m']):
            raise ValueError('Branch actor/frame source join changed')
    road = ET.parse(source/'road.xodr').getroot()
    signals = road.findall('.//signal')
    context = json.loads((source/'road-context.json').read_text())
    if suffix == 'device_controlled':
        if len(signals)!=1 or context['authored_device_count']!=1 or \
                any(row['authored_official_device_count']!=1 for row in rows):
            raise ValueError('Authored device branch missing')
        if any(row['opposing_approaches'] or row['other_left_turn_intent'] for row in rows):
            raise ValueError('Device branch changed approach geometry')
    else:
        turning = suffix == 'opposing_left_turn'
        if signals or context['other_highway_roads']!=context['ego_highway_roads'] or \
                not all(row['opposing_approaches'] and
                        row['other_left_turn_intent']==turning for row in rows):
            raise ValueError('Opposing branch context changed')
        first,last = rows[0]['other'],rows[250]['other']
        if first['center_xyz_m'][0] <= 40 or last['center_xyz_m'][0] > 0:
            raise ValueError('Opposing trajectory does not cross junction')
        if turning and (last['center_xyz_m'][1]>=0 or
                        last['yaw_rad']<=math.pi):
            raise ValueError('Requested left turn absent from actor source')
        if not turning and (last['center_xyz_m'][1]!=1.75 or
                            last['yaw_rad']!=round(math.pi,9)):
            raise ValueError('No-turn control changed direction')
    if context['official_device_governance_verified'] or \
            context['opposite_direction_left_turn_exclusion_resolved'] or \
            context['subsection_4_exception_resolved'] or \
            context['original_native_observed'] or context['legal_verdict'] is not None:
        raise ValueError('Branch diagnostic asserted unresolved legal/Native fact')
    return {'case_id':history['case_id'],'frames':600,
            'actor_history_sha256':sha(source/'actor-history.json'),
            'road_sha256':sha(source/'road.xodr'),
            'source_inventory_sha256':sha(root/'source-inventory.json'),
            'original_native_observed':False,'legal_verdict':None}


if __name__ == '__main__':
    if len(sys.argv)!=2:
        raise SystemExit('one branch suffix required')
    print(json.dumps(audit(sys.argv[1]),sort_keys=True))
