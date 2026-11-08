"""Independently recompute copied paragraph (b) pairs and provenance."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from fixture_raw import build as build_raw
from prepare_raw import prepare
from measure_prepared import measure as measure_prepared

HERE=Path(__file__).resolve().parent
CASE=HERE.parent.parent
ROOT=CASE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def audit():
    manifest=read(HERE/'manifest.json')
    offline=read(HERE/'offline/manifest.json')
    proof=read(HERE/'offline/proof-compatibility.json')
    if proof['positives']!=40 or proof['negatives']!=80 or len(offline['entries'])!=8:
        raise ValueError('copied proof counts')
    if offline['construction_sha256']!=sha(HERE/'manifest.json'):
        raise ValueError('construction provenance')
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    if manifest['assignment_sha256']!=sha(assignment) or manifest['case_plan_sha256']!=sha(plan):
        raise ValueError('frozen input provenance')
    if manifest['road_sha256']!=sha(HERE/'four-lane-pass.xodr'):
        raise ValueError('road provenance')
    if manifest['capture_sha256']!=sha(HERE/'capture.py') or \
            manifest['measurement_contract_sha256']!=sha(HERE/'measurement-contract.json'):
        raise ValueError('capture or measurement provenance')
    seen={};all_rows={};measurements={};raw_rows=0
    for entry in offline['entries']:
        bundle=HERE/entry['bundle']
        witness=entry['case_id'].split('__')[-1]
        candidate=entry['candidate_id']
        sources={
            'assignment-source.json':assignment,
            'case-plan.json':plan,
            'four-lane-pass.xodr':HERE/'four-lane-pass.xodr',
            'config.json':HERE/'drafts'/witness/candidate/'config.json',
            'requested-tracks.jsonl':HERE/'drafts'/witness/candidate/'requested-tracks.jsonl',
            'build.py':HERE/'build.py','check.py':HERE/'check.py',
            'capture.py':HERE/'capture.py',
            'measurement-contract.json':HERE/'measurement-contract.json',
            'measure_saved.py':HERE/'measure_saved.py',
            'route_fallbacks.py':HERE/'route_fallbacks.py',
            'fixture_raw.py':HERE/'fixture_raw.py',
            'prepare_raw.py':HERE/'prepare_raw.py',
            'measure_prepared.py':HERE/'measure_prepared.py',
            'saved/native-observed.jsonl':HERE/'saved-fixtures'/witness/candidate/'native-observed.jsonl',
            'saved/camera-frames.jsonl':HERE/'saved-fixtures'/witness/candidate/'camera-frames.jsonl',
            'saved/readback.json':HERE/'saved-fixtures'/witness/candidate/'readback.json'}
        if set(entry['file_sha256'])!=set(sources):
            raise ValueError('copied file set')
        for name,source in sources.items():
            if sha(bundle/name)!=sha(source) or entry['file_sha256'][name]!=sha(source):
                raise ValueError('copied provenance: '+name)
        cfg=read(bundle/'config.json')
        track=rows(bundle/'requested-tracks.jsonl')
        road=ET.parse(bundle/'four-lane-pass.xodr').getroot()
        lane_ids=[int(n.attrib['id']) for n in road.findall('./road/lanes/laneSection/left/lane')+
            road.findall('./road/lanes/laneSection/right/lane')]
        if sorted(lane_ids)!=[-2,-1,1,2] or len(track)!=240:
            raise ValueError('four-lane or frame count')
        parked=witness=='exception_2_1'
        speed=7 if candidate=='fallback1' else 8
        stop=45 if candidate=='fallback3' else None
        camera='elevated_overview' if candidate=='fallback2' else 'standard'
        if cfg['parked_vehicle_requested']!=parked or cfg['requested_ego_speed_mps']!=speed or cfg['camera_policy']!=camera or cfg['stop_x_m']!=stop:
            raise ValueError('candidate policy')
        for i,row in enumerate(track):
            t=(i+1)/20;x=min(stop or 300,5+speed*t)
            blend=max(0,min(1,(x-15)/20,(105-x)/20))
            y=-1.75-3.5*blend
            if not (row['frame']==i and row['road_id']==211 and
                    math.isclose(row['ego_x_m'],x,abs_tol=1e-6) and
                    math.isclose(row['ego_y_m'],y,abs_tol=1e-6) and
                    math.isclose(row['lead_x_m'],35+4*t,abs_tol=1e-6) and
                    row['parked_vehicle_requested']==parked and
                    row['parked_x_m']==(55 if parked else None) and
                    row['parked_y_m']==(-6.8 if parked else None) and
                    row['actual_right_pass_observed'] is False and
                    row['legal_verdict'] is None):
                raise ValueError(f'paragraph (b) row {witness} {candidate} {i}')
        seen[(witness,candidate)]=cfg
        all_rows[(witness,candidate)]=track
        saved_rows=rows(bundle/'saved/native-observed.jsonl')
        camera_rows=rows(bundle/'saved/camera-frames.jsonl')
        receipt=read(bundle/'saved/readback.json')
        if len(saved_rows)!=240 or len(camera_rows)!=240 or \
                receipt['native_observed_sha256']!=sha(bundle/'saved/native-observed.jsonl') or \
                receipt['camera_frames_sha256']!=sha(bundle/'saved/camera-frames.jsonl'):
            raise ValueError('saved source binding')
        pass_frames=0
        for i,(request,row,camera) in enumerate(zip(track,saved_rows,camera_rows)):
            x,y=request['ego_x_m'],request['ego_y_m']
            body=[[round(x+dx,6),round(y+dy,6)] for dx,dy in
                  ((-2,-.9),(-2,.9),(2,.9),(2,-.9))]
            if not(row['frame']==camera['frame']==i and
                   row['ego_body_xy_m']==body and
                   row['ego_center_xy_m']==[x,y] and
                   row['parked_actor_id']==(103 if parked else None) and
                   row['parked_speed_mps']==(0 if parked else None) and
                   camera['forward_frame']==camera['overview_frame']==i and
                   row['parked_pixels_reviewed'] is False and
                   row['lane_pixels_reviewed'] is False):
                raise ValueError(f'independent saved row {i}')
            lead_x=request['lead_x_m']
            pass_frames+=int(min(p[0] for p in body)>lead_x+2 and
                all(-7<=p[1]<=-3.5 for p in body))
        measurements[(witness,candidate)]=pass_frames
        with tempfile.TemporaryDirectory() as temporary:
            temporary=Path(temporary)
            raw=temporary/'raw';prepared=temporary/'prepared'
            build_raw(bundle,raw)
            receipt=prepare(bundle,raw,prepared,synthetic_cpu=True)
            measured=measure_prepared(bundle,prepared)
            if (receipt['source_kind']!='synthetic_cpu' or
                receipt['raw_hashes']!={name:sha(raw/name) for name in
                    ('native-map-readback.json','native-raw-actors.jsonl',
                     'video_frames.jsonl','frame-review.jsonl',
                     'native-capture-report.json')} or
                measured['full_body_right_pass_frames']!=pass_frames or
                measured['parked_actor_frames']!=(240 if parked else 0) or
                measured['human_reviewed_condition_frames']!=0):
                raise ValueError('raw-to-saved independent receipt')
            raw_actor=rows(raw/'native-raw-actors.jsonl')
            saved_actor=rows(prepared/'native-observed.jsonl')
            frames=rows(prepared/'camera-frames.jsonl')
            reviews=rows(prepared/'frame-review.jsonl')
            for i,(original,converted,frame,view) in enumerate(zip(
                    raw_actor,saved_actor,frames,reviews)):
                if not(original['frame']==converted['frame']==frame['frame']==view['frame']==i and
                    original['native_frame']==converted['native_frame']==frame['native_frame']==view['native_frame'] and
                    original['ego']==converted['ego'] and
                    original['lead']==converted['lead'] and
                    original['parked_vehicle']==converted['parked_vehicle'] and
                    view['review_provenance']=='synthetic_cpu'):
                    raise ValueError(f'independent raw-to-saved row {i}')
                raw_rows+=1
    if len(seen)!=8:raise ValueError('pair coverage')
    if any((measurements[(witness,candidate)]==0)!=(candidate=='fallback3')
           for witness in ('exception_2_1','exception_2_2')
           for candidate in ('primary','fallback1','fallback2','fallback3')):
        raise ValueError('independent saved pass/stop split')
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        absent=all_rows[('exception_2_1',candidate)]
        present=all_rows[('exception_2_2',candidate)]
        for left,right in zip(absent,present):
            for key in ('frame','time_s','ego_x_m','ego_y_m','ego_lane_id',
                        'lead_x_m','lead_y_m','lead_lane_id','road_id'):
                if left[key]!=right[key]:raise ValueError('controlled pair differs: '+key)
            if not left['parked_vehicle_requested'] or right['parked_vehicle_requested']:
                raise ValueError('parked control differs')
    result={'format':'c146314-paragraph-b-independent-package-audit-v1',
        'bundles':8,'controlled_pairs':4,'request_rows_recomputed':1920,
        'saved_rows_recomputed':1920,
        'raw_to_saved_rows_recomputed':raw_rows,
        'right_pass_frames_by_candidate':{
            candidate:measurements[('exception_2_2',candidate)]
            for candidate in ('primary','fallback1','fallback2','fallback3')},
        'copied_positives':40,'rejected_negatives':80,
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'offline/package-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    print(json.dumps(audit()))
