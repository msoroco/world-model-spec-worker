"""Build labelled synthetic paragraph (a) saved light-state controls."""
import hashlib
import json
from pathlib import Path
import shutil

BRANCH=Path(__file__).resolve().parent
NATIVE=BRANCH.parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def write_rows(path,values):
    path.write_text(''.join(json.dumps(x,sort_keys=True,allow_nan=False)+'\n'
                            for x in values))

def build():
    entries=[]
    for witness in ('exception_1_1','exception_1_2'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle=BRANCH/'drafts'/witness/candidate
            cfg=read(bundle/'config.json')
            source=NATIVE/'saved-fixtures/witness_1'/candidate
            target=BRANCH/'saved-fixtures'/witness/candidate
            target.mkdir(parents=True,exist_ok=True)
            for name in ('native-observed.jsonl','camera-frames.jsonl'):
                shutil.copy2(source/name,target/name)
            geometry=read(source/'readback.json')
            geometry.update(config_sha256=sha(bundle/'config.json'),
                tracks_sha256=cfg['tracks_sha256'],
                observed_sha256=sha(target/'native-observed.jsonl'),
                camera_sha256=sha(target/'camera-frames.jsonl'))
            write(target/'readback.json',geometry)
            signal=cfg['lead_left_signal_requested'];light=[];review=[]
            for i in range(240):
                t=(i+1)/20
                light.append({'frame':i,'native_frame':1000+i,'time_s':t,
                    'source_kind':'synthetic_cpu','lead_actor_id':2,
                    'observed_lead_left_blinker':signal})
                review.append({'frame':i,'native_frame':1000+i,'time_s':t,
                    'source_kind':'synthetic_cpu','review_provenance':'synthetic_cpu',
                    'signal_pixel_reviewed':False,'lead_left_signal_visible':None})
            write_rows(target/'lead-light-observed.jsonl',light)
            write_rows(target/'signal-review.jsonl',review)
            write(target/'signal-readback.json',{
                'format':'c146314-paragraph-a-signal-readback-v1',
                'source_kind':'synthetic_cpu',
                'config_sha256':sha(bundle/'config.json'),
                'tracks_sha256':cfg['tracks_sha256'],
                'geometry_readback_sha256':sha(target/'readback.json'),
                'light_sha256':sha(target/'lead-light-observed.jsonl'),
                'review_sha256':sha(target/'signal-review.jsonl'),
                'original_native_observed':False,
                'signal_pixel_reviewed':False,'legal_verdict':None,
                'delivery_ready':False})
            entries.append({'case_id':cfg['case_id'],'candidate_id':candidate,
                'saved_dir':str(target.relative_to(BRANCH)),
                'sha256':{name:sha(target/name) for name in
                    ('native-observed.jsonl','camera-frames.jsonl','readback.json',
                     'lead-light-observed.jsonl','signal-review.jsonl',
                     'signal-readback.json')}})
    write(BRANCH/'saved-fixtures/manifest.json',{
        'format':'c146314-paragraph-a-synthetic-saved-v1',
        'entries':entries,'original_native_observed':False,
        'delivery_ready':False})
    return entries

if __name__=='__main__':print(json.dumps({'fixtures':len(build())}))
