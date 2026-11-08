"""Measure synthetic paragraph (a) light state and right-pass geometry."""
import argparse
import hashlib
import json
from pathlib import Path

from geometry_saved import measure as geometry_measure

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)

def measure(bundle,saved):
    bundle,saved=Path(bundle),Path(saved)
    cfg=read(bundle/'config.json')
    geometry=geometry_measure(bundle,saved)
    back=read(saved/'signal-readback.json')
    light=rows(saved/'lead-light-observed.jsonl')
    review=rows(saved/'signal-review.jsonl')
    require(back['format']=='c146314-paragraph-a-signal-readback-v1' and
        back['source_kind']=='synthetic_cpu' and
        back['config_sha256']==sha(bundle/'config.json') and
        back['tracks_sha256']==cfg['tracks_sha256'] and
        back['geometry_readback_sha256']==sha(saved/'readback.json') and
        back['light_sha256']==sha(saved/'lead-light-observed.jsonl') and
        back['review_sha256']==sha(saved/'signal-review.jsonl') and
        back['original_native_observed'] is False and
        back['signal_pixel_reviewed'] is False and
        back['legal_verdict'] is None and
        back['delivery_ready'] is False and
        len(light)==len(review)==240,
        'signal/readback source binding')
    observed=0;mismatch=0;pixel_reviewed=0
    for i,(row,view) in enumerate(zip(light,review)):
        t=(i+1)/20
        require(row['frame']==view['frame']==i and
            row['native_frame']==view['native_frame']==1000+i and
            row['time_s']==view['time_s']==t and
            row['source_kind']==view['source_kind']=='synthetic_cpu' and
            row['lead_actor_id']==2 and
            type(row['observed_lead_left_blinker']) is bool and
            view['review_provenance']=='synthetic_cpu' and
            view['signal_pixel_reviewed'] is False and
            view['lead_left_signal_visible'] is None,
            f'synthetic signal/video join {i}')
        observed+=int(row['observed_lead_left_blinker'])
        mismatch+=int(row['observed_lead_left_blinker']!=
                      cfg['lead_left_signal_requested'])
        pixel_reviewed+=int(view['signal_pixel_reviewed'])
    return {'format':'c146314-paragraph-a-saved-measurement-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':'synthetic_cpu','frames':240,
        'observed_lead_left_blinker_frames':observed,
        'requested_signal_mismatch_frames':mismatch,
        'signal_pixel_reviewed_frames':pixel_reviewed,
        'passing_right_geometry_frames':geometry['passing_right_geometry_frames'],
        'original_native_observed':False,'accepted':False,
        'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved-dir',type=Path,required=True)
    a=p.parse_args();print(json.dumps(measure(a.bundle,a.saved_dir),indent=2))
