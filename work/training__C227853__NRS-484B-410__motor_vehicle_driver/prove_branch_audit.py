"""Exercise branch-specific independent review joins on source-shaped fixtures."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from delivery_audit import check_review

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(suffix):
    folder=HERE/'selected-source'/suffix
    frame_map=folder/'video_frames.jsonl'
    context=folder/'departure-context.json'
    samples=folder/'departure-trace.jsonl'
    sourced=json.loads(context.read_text())
    with tempfile.TemporaryDirectory(prefix='c227853-review-',
                                     dir=os.environ['TMPDIR']) as temporary:
        authority=Path(temporary)/'authority.json'
        authority.write_text('{"diagnostic_only":true}\n')
        review={'format':'c227853-original-departure-review-v1',
                'source_kind':'original_native_review',
                'case_id':HERE.name+'__'+suffix,'reviewer_id':'synthetic-cpu-review-test',
                'video_frames_sha256':sha(frame_map),
                'departure_context_sha256':sha(context),
                'departure_trace_sha256':sha(samples),
                'authority_manifest_sha256':sha(authority),
                'parking_permitted_value':sourced['parking_permitted'],
                'initial_status_value':sourced['initial_status'],
                'reviewed_frames':[150],
                'public_highway_verified':True,
                'curb_permission_fact_verified':True,
                'initial_status_verified':True,
                'initial_footprint_within_highway_verified':True,
                'movement_onset_reviewed':True,
                'nearby_traffic_reviewed':True}
        check_review(review,review['case_id'],frame_map,context,samples,authority)
        for key,value in (('parking_permitted_value',not sourced['parking_permitted']),
                          ('initial_status_value','wrong')):
            broken=dict(review)
            broken[key]=value
            try:
                check_review(broken,review['case_id'],frame_map,context,samples,authority)
            except ValueError as error:
                if 'finding differs' not in str(error):
                    raise
            else:
                raise AssertionError('Damaged original authority review accepted: '+key)
    return {'case_id':review['case_id'],'status':sourced['initial_status'],
            'parking_permitted':sourced['parking_permitted'],'passed':True}


if __name__=='__main__':
    print(json.dumps({'passed':True,'checks':[verify('controlled_'+str(i))
                                              for i in range(1,13)]},sort_keys=True))
