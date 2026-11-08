"""Retain labelled synthetic C135709 actor and camera observations."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
NATIVE=CASE/'native'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')
def write_rows(path,items):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x)+'\n' for x in items))

def build():
    entries=[]
    for witness in ('reference','contrast'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            source=NATIVE/'drafts'/witness/candidate
            cfg=json.loads((source/'config.json').read_text())
            requests=rows(source/'requested-tracks.jsonl')
            saved=NATIVE/'saved-fixtures'/witness/candidate
            observed=[];camera=[];review=[]
            for row in requests:
                i=row['frame'];x=row['ego_x_m'];y=row['ego_y_m']
                body=[[round(x+dx,6),round(y+dy,6)]
                      for dx,dy in ((2.3,.9),(2.3,-.9),(-2.3,.9),(-2.3,-.9))]
                observed.append({'frame':i,'native_frame':1000+i,
                    'time_s':row['time_s'],'source_kind':'synthetic_cpu',
                    'witness':witness,'candidate_id':candidate,
                    'road_id':517,'lane_id':row['lane_id'],
                    'phase':row['phase'],'ego_actor_id':135709,
                    'ego_blueprint':'vehicle.tesla.model3',
                    'ego_x_m':x,'ego_y_m':y,'ego_heading_deg':0,
                    'ego_speed_mps':row['ego_speed_mps'],
                    'ego_body_xy_m':body,
                    'actual_parking_observed':False})
                camera.append({'frame':i,'camera_frame':1000+i,
                    'time_s':row['time_s'],'source_kind':'synthetic_cpu',
                    'stand_sign_visible':True,'stand_polygon_visible':True})
                review.append({'frame':i,'native_frame':1000+i,
                    'time_s':row['time_s'],'source_kind':'synthetic_cpu',
                    'reviewed_ego_y_m':y,'review_provenance':'synthetic_cpu'})
            write_rows(saved/'native-observed.jsonl',observed)
            write_rows(saved/'camera-frames.jsonl',camera)
            write_rows(saved/'stand-review.jsonl',review)
            write(saved/'stand-readback.json',{
                'source_kind':'synthetic_cpu','road_sha256':cfg['road_sha256'],
                'request_sha256':cfg['tracks_sha256'],
                'review_sha256':sha(saved/'stand-review.jsonl'),
                'stand_polygon_x_m':[50,75],'stand_polygon_y_m':[-8.25,-3.5],
                'sign_text':'TAXICAB STAND',
                'official_designation_verified':False,
                'sign_appropriateness_verified':False,
                'non_taxicab_actual_use_verified':False,
                'passenger_loading_exception_verified':False,
                'actual_parking_observed':False,'legal_verdict':None})
            entries.append({'case_id':cfg['case_id'],'candidate_id':candidate,
                'sha256':{name:sha(saved/name) for name in
                    ('native-observed.jsonl','camera-frames.jsonl','stand-review.jsonl','stand-readback.json')}})
    manifest={'format':'c135709-synthetic-saved-manifest-v1',
        'entries':entries,'original_native_observed':False,'delivery_ready':False}
    write(NATIVE/'saved-manifest.json',manifest)
    return manifest

if __name__=='__main__':print(json.dumps({'fixtures':len(build()['entries'])}))
