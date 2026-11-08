"""Independently recompute paragraph (c)(1) boundary requests and copies."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
CASE=HERE.parent.parent
ROOT=CASE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines()]


def audit():
    construction=read(HERE/'manifest.json')
    offline=read(HERE/'offline/manifest.json')
    proof=read(HERE/'offline/proof-compatibility.json')
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    if not (construction['assignment_sha256']==sha(assignment) and
        construction['case_plan_sha256']==sha(plan) and
        construction['road_sha256']==sha(HERE/'unmarked-pass.xodr') and
        construction['capture_sha256']==sha(HERE/'capture.py') and
        construction['saved_sha256']==sha(HERE/'saved.py') and
        construction['fixture_raw_sha256']==sha(HERE/'fixture_raw.py') and
        construction['measurement_contract_sha256']==sha(HERE/'measurement-contract.json') and
        offline['construction_sha256']==sha(HERE/'manifest.json') and
        proof['positives']==16 and proof['negatives']==40 and
        len(offline['entries'])==8):
        raise ValueError('construction/proof provenance')
    text=read(plan)['source_law']['text']
    if not ('more than 200 feet' in text and
        'not marked as a traffic lane; or (2)' in text and
        'intersection or past any private way' in text):
        raise ValueError('disjunctive statutory source')
    seen={};all_rows={}
    for entry in offline['entries']:
        witness=entry['case_id'].split('__')[-1]
        candidate=entry['candidate_id']
        bundle=HERE/entry['bundle']
        sources={
            'assignment-source.json':assignment,'case-plan.json':plan,
            'unmarked-pass.xodr':HERE/'unmarked-pass.xodr',
            'config.json':HERE/'drafts'/witness/candidate/'config.json',
            'requested-tracks.jsonl':HERE/'drafts'/witness/candidate/'requested-tracks.jsonl',
            'build.py':HERE/'build.py','check.py':HERE/'check.py',
            'capture.py':HERE/'capture.py',
            'measurement-contract.json':HERE/'measurement-contract.json',
            'saved.py':HERE/'saved.py','fixture_raw.py':HERE/'fixture_raw.py'}
        if set(sources)!=set(entry['file_sha256']):
            raise ValueError('copy set')
        for name,source in sources.items():
            if sha(bundle/name)!=sha(source) or entry['file_sha256'][name]!=sha(source):
                raise ValueError('copied byte provenance '+name)
        road=ET.parse(bundle/'unmarked-pass.xodr').getroot()
        lanes=road.findall('./road/lanes/laneSection/right/lane')
        if road.find('./road').attrib['id']!='212' or \
            [(n.attrib['id'],n.attrib['type']) for n in lanes]!=[
                ('-1','driving'),('-2','shoulder')]:
            raise ValueError('independent road geometry')
        cfg=read(bundle/'config.json');track=rows(bundle/'requested-tracks.jsonl')
        distance=61.06 if witness=='exception_3_1' else 60.96
        speed=7 if candidate=='fallback1' else 8
        stop=45 if candidate=='fallback3' else None
        exit_x=20+distance
        if (len(track)!=240 or cfg['requested_excursion_m']!=distance or
            cfg['requested_c1_within_200ft']!=(distance<=60.96) or
            cfg['c2_crossing_verified'] is not False or
            cfg['actual_excursion_observed'] is not False):
            raise ValueError('independent numerical/control policy')
        for i,row in enumerate(track):
            t=(i+1)/20;x=min(stop or 300,5+speed*t)
            blend=max(0,min(1,(x-16.2)/5,(exit_x+3.8-x)/5))
            if not(row['frame']==i and row['road_id']==212 and
                math.isclose(row['ego_x_m'],x,abs_tol=1e-6) and
                math.isclose(row['ego_y_m'],-1.75-3.5*blend,abs_tol=1e-6) and
                row['requested_excursion_m']==distance and
                row['private_way_or_intersection_crossing_verified'] is False and
                row['legal_verdict'] is None):
                raise ValueError(f'independent request row {i}')
        seen[(witness,candidate)]=cfg
        all_rows[(witness,candidate)]=track
    if len(seen)!=8:raise ValueError('candidate coverage')
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        high=all_rows[('exception_3_1',candidate)]
        edge=all_rows[('exception_3_2',candidate)]
        for a,b in zip(high,edge):
            for key in ('frame','time_s','ego_x_m','lead_x_m','lead_y_m'):
                if a[key]!=b[key]:raise ValueError('boundary pair control '+key)
            if round(a['requested_excursion_m']-b['requested_excursion_m'],6)!=.1:
                raise ValueError('boundary gap')
    result={'format':'c146314-paragraph-c1-independent-audit-v1',
        'bundles':8,'controlled_pairs':4,'rows_recomputed':1920,
        'boundary_m':60.96,'above_boundary_m':61.06,
        'copied_positives':16,'rejected_negatives':40,
        'paragraph_c2_verified':False,'original_native_observed':False,
        'delivery_ready':False}
    (HERE/'offline/package-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit()))
