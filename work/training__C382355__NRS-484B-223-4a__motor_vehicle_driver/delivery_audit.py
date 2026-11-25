"""Audit source joins for CPU fixtures and reject unobserved Native delivery."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]


def check(case_id,diagnostic):
    manifest=json.loads((HERE/'selected-probe-manifest.json').read_text())
    entry=next((x for x in manifest['cases'] if x['case_id']==case_id),None)
    if entry is None:raise ValueError('Select one exact case')
    if not diagnostic:
        raise ValueError('Original Native right-only lane, movement pixels and purpose review required for delivery acceptance')
    suffix=case_id.rsplit('__',1)[-1]
    source=HERE/'selected-source'/suffix
    samples=rows(source/'native_samples.jsonl')
    evidence=rows(source/'capture/evidence.jsonl')
    trace=rows(source/'trace.jsonl')
    video=rows(source/'video_frames.jsonl')
    if any(len(x)!=480 for x in (samples,evidence,trace,video)):
        raise ValueError('Incomplete 480-frame source join')
    for i,(native,world,kin,frame) in enumerate(zip(samples,evidence,trace,video)):
        expected=100+i
        projection=world['world']['road_projection']
        if (native['native_frame']!=expected or world['original_frame']!=expected or
                kin['frame']!=expected or frame['native_frame']!=expected or
                (projection['road_id'],projection['lane_id'])!=
                (native['native_road_id'],native['native_lane_id'])):
            raise ValueError('Native/source frame or lane projection mismatch')
    receipt=json.loads((HERE/'selected-proofs'/f'{suffix}-primary-compatibility.json').read_text())
    saved=json.loads((HERE/'selected-proofs'/f'{suffix}-primary-processing.json').read_text())
    if (receipt['case_id']!=case_id or receipt['construction_sha256']!=entry['construction_sha256'] or
            not receipt['passed'] or not {'four_camera_sources','lean_decoder','final_decode',
                                          'selected_measurements','negative_case_source'}<=set(receipt['checks'])):
        raise ValueError('Selected public proof incomplete')
    if not saved['passed'] or not saved['recorded_only'] or saved['physical_acceptance_claimed']:
        raise ValueError('Recorded-only saved proof incomplete')
    return {'case_id':case_id,'joined_frames':480,'diagnostic_only':True,
            'original_native_observed':False,'physical_acceptance':False,'legal_verdict':None,
            'source_sha256':sha(source/'native_samples.jsonl'),
            'compatibility_sha256':sha(HERE/'selected-proofs'/f'{suffix}-primary-compatibility.json'),
            'saved_sha256':sha(HERE/'selected-proofs'/f'{suffix}-primary-processing.json')}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--diagnostic',action='store_true')
    a=p.parse_args();print(json.dumps(check(a.case,a.diagnostic),sort_keys=True))
