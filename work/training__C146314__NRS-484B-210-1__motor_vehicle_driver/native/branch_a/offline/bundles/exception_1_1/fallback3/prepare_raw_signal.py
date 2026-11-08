"""Carry observed Native lead indicator and review through source-bound preparation."""
import argparse
import hashlib
import json
from pathlib import Path

from prepare_raw_geometry import prepare as prepare_geometry

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)
def write_rows(path,items):
    Path(path).write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in items))

def prepare(bundle,raw,output,synthetic_cpu=False):
    bundle,raw,output=map(Path,(bundle,raw,output))
    cfg=read(bundle/'config.json')
    geometry=prepare_geometry(bundle,raw,output,synthetic_cpu)
    actors=rows(raw/'native-raw-actors.jsonl')
    reviews=rows(raw/'frame-review.jsonl')
    saved=rows(output/'native-observed.jsonl')
    kind='synthetic_cpu' if synthetic_cpu else 'original_native'
    require(len(actors)==len(reviews)==len(saved)==240,
            'paragraph (a) raw signal coverage')
    light=[];signal_review=[]
    for i,(a,r,s) in enumerate(zip(actors,reviews,saved)):
        observed=a.get('observed_lead_left_blinker')
        visible=r.get('lead_left_signal_visible')
        reviewed=r.get('signal_pixel_reviewed')
        require(a['frame']==r['frame']==s['frame']==i and
            a['native_frame']==r['native_frame']==s['native_frame'] and
            a['time_s']==r['time_s']==s['time_s'] and
            a.get('requested_lead_left_signal') is cfg['lead_left_signal_requested'] and
            type(observed) is bool and
            type(a.get('observed_lead_light_state')) is int and
            a['observed_lead_light_state']>=0 and
            type(reviewed) is bool and
            (type(visible) is bool if reviewed else visible is None) and
            r['source_kind']==kind and
            r['review_provenance']==('synthetic_cpu' if synthetic_cpu
                                    else 'human_frame_review'),
            f'paragraph (a) raw signal/review join {i}')
        light.append({'frame':i,'native_frame':a['native_frame'],
            'time_s':a['time_s'],'source_kind':kind,
            'lead_actor_id':s['lead']['actor_id'],
            'observed_lead_left_blinker':observed,
            'observed_lead_light_state':a['observed_lead_light_state']})
        signal_review.append({'frame':i,'native_frame':r['native_frame'],
            'time_s':r['time_s'],'source_kind':kind,
            'review_provenance':r['review_provenance'],
            'signal_pixel_reviewed':reviewed,
            'lead_left_signal_visible':visible})
    write_rows(output/'lead-light-observed.jsonl',light)
    write_rows(output/'signal-review.jsonl',signal_review)
    receipt={'format':'c146314-paragraph-a-raw-signal-preparation-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':kind,'config_sha256':sha(bundle/'config.json'),
        'geometry_receipt_sha256':sha(output/'preparation-receipt.json'),
        'raw_actor_sha256':sha(raw/'native-raw-actors.jsonl'),
        'raw_review_sha256':sha(raw/'frame-review.jsonl'),
        'light_sha256':sha(output/'lead-light-observed.jsonl'),
        'review_sha256':sha(output/'signal-review.jsonl'),
        'original_native_observed':not synthetic_cpu,
        'signal_pixel_reviewed':all(x['signal_pixel_reviewed']
                                    for x in signal_review),
        'legal_verdict':None,
        'delivery_ready':False}
    (output/'signal-preparation-receipt.json').write_text(
        json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--raw-folder',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--synthetic-cpu',action='store_true')
    a=p.parse_args()
    print(json.dumps(prepare(a.bundle,a.raw_folder,a.output_dir,a.synthetic_cpu),indent=2))
