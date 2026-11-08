"""Measure prepared Native indicator observations without legal promotion."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_prepared_geometry import measure as measure_geometry

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)

def measure(bundle,saved):
    bundle,saved=Path(bundle),Path(saved)
    cfg=read(bundle/'config.json')
    geometry=measure_geometry(bundle,saved)
    receipt=read(saved/'signal-preparation-receipt.json')
    light=rows(saved/'lead-light-observed.jsonl')
    review=rows(saved/'signal-review.jsonl')
    require(receipt['config_sha256']==sha(bundle/'config.json') and
        receipt['geometry_receipt_sha256']==sha(saved/'preparation-receipt.json') and
        receipt['light_sha256']==sha(saved/'lead-light-observed.jsonl') and
        receipt['review_sha256']==sha(saved/'signal-review.jsonl') and
        receipt['source_kind']==geometry['source_kind'] and
        receipt['original_native_observed']==geometry['original_native_observed'] and
        receipt['legal_verdict'] is None and
        receipt['delivery_ready'] is False and len(light)==len(review)==240,
        'prepared signal receipt/source binding')
    observed=mismatch=reviewed=0
    for i,(a,r) in enumerate(zip(light,review)):
        require(a['frame']==r['frame']==i and
            a['native_frame']==r['native_frame'] and
            a['time_s']==r['time_s'] and
            a['source_kind']==r['source_kind']==receipt['source_kind'] and
            type(a['observed_lead_left_blinker']) is bool and
            type(a['observed_lead_light_state']) is int and
            type(r['signal_pixel_reviewed']) is bool and
            (type(r['lead_left_signal_visible']) is bool if
             r['signal_pixel_reviewed'] else r['lead_left_signal_visible'] is None),
            f'prepared signal/video join {i}')
        observed+=int(a['observed_lead_left_blinker'])
        mismatch+=int(a['observed_lead_left_blinker']!=
                      cfg['lead_left_signal_requested'])
        reviewed+=int(r['signal_pixel_reviewed'])
    return {'format':'c146314-paragraph-a-prepared-signal-measurement-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':receipt['source_kind'],'frames':240,
        'observed_lead_left_blinker_frames':observed,
        'requested_signal_mismatch_frames':mismatch,
        'signal_pixel_reviewed_frames':reviewed,
        'passing_right_geometry_frames':
            geometry['ego_body_ahead_and_right_of_lead_frames'],
        'original_native_observed':receipt['original_native_observed'],
        'accepted':False,'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved-dir',type=Path,required=True)
    a=p.parse_args();print(json.dumps(measure(a.bundle,a.saved_dir),indent=2))
