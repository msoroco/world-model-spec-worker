"""Independently audit the closed roundabout and 1,920 authored request rows."""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def audit():
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    source=json.loads(assignment.read_text())
    if (source['law_record']['text']!=
        'The following regulations pertain to the operation of vehicles within a roundabout: The operator of a vehicle who intends to exit a roundabout: Shall use the right lane to turn right.' or
        source['local_snapshot']['memberships']['full-train']):
        raise ValueError('C132497 exact law or accepted membership differs')
    road_path=HERE/'right-exit-road.xodr'
    draft=HERE/'ccw-right-exit-draft.xodr'
    if sha(road_path)!=sha(draft):
        raise ValueError('C132497 active road differs from independently audited CCW design')
    audit=subprocess.run([sys.executable,str(HERE/'audit_ccw_design.py')],
        capture_output=True,text=True)
    if audit.returncode:
        raise ValueError('C132497 CCW geometry audit failed: '+audit.stderr[-1000:])
    audit_receipt=json.loads((HERE/'ccw-design-audit.json').read_text())
    if (audit_receipt.get('road_sha256')!=sha(road_path) or
        audit_receipt.get('positive',{}).get('counterclockwise_arc_ids')!=[21,23] or
        len(audit_receipt.get('negative',{}))!=3):
        raise ValueError('C132497 CCW geometry receipt differs')
    manifest=json.loads((HERE/'manifest.json').read_text())
    if len(manifest['entries'])!=8 or manifest['road_sha256']!=sha(road_path):
        raise ValueError('C132497 construction manifest differs')
    checked=0;exit_requests=0
    for item in manifest['entries']:
        witness=item['case_id'].removeprefix(CASE.name+'__');candidate=item['candidate_id']
        folder=HERE/'drafts'/witness/candidate
        config=json.loads((folder/'config.json').read_text())
        track=rows(folder/'requested-tracks.jsonl')
        if (len(track)!=240 or item['config_sha256']!=sha(folder/'config.json') or
            item['tracks_sha256']!=sha(folder/'requested-tracks.jsonl') or
            item['controller_intention_sha256']!=sha(folder/'controller-intention.json') or
            config['controller_intention_sha256']!=sha(folder/'controller-intention.json') or
            config['assignment_sha256']!=sha(assignment) or
            config['road_sha256']!=sha(road_path)):
            raise ValueError('C132497 construction source hashes differ')
        road_sequence=[x['road_id'] for x in track]
        if road_sequence!=sorted(road_sequence):
            raise ValueError('C132497 requested phase order reverses')
        if set(road_sequence)!={20,21,22}:
            raise ValueError('C132497 authored exit request incomplete')
        if candidate=='fallback3' and (any(track[i]['ego_speed_mps']!=0 for i in range(40)) or
            track[40]['ego_speed_mps']<=0):
            raise ValueError('C132497 dwell fallback timing differs')
        exit_requests+=22 in road_sequence;checked+=len(track)
    result={'format':'c132497-independent-construction-audit-v1',
        'road_sha256':sha(road_path),'request_rows_checked':checked,
        'authored_exit_requests':exit_requests,
        'complete_circle_xml_geometry_authored':True,
        'circulation_direction':'counterclockwise',
        'original_native_observed':False,
        'delivery_ready':False}
    (HERE/'construction-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
