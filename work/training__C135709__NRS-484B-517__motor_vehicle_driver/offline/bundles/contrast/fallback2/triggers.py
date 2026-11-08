"""Route C135709 fallback requests from source-bound saved visibility and review."""
import argparse
import hashlib
import json
from pathlib import Path

import measure_saved

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def route(bundle,saved_dir=None):
    bundle=Path(bundle);saved=Path(saved_dir) if saved_dir else bundle/'saved'
    if saved_dir:
        # Reuse the exact copied processor with only the measured saved folder replaced.
        import tempfile,shutil
        with tempfile.TemporaryDirectory() as temporary:
            copy=Path(temporary)/'bundle';shutil.copytree(bundle,copy)
            shutil.rmtree(copy/'saved');shutil.copytree(saved,copy/'saved')
            measurement=measure_saved.measure(copy)
    else:measurement=measure_saved.measure(bundle)
    request=rows(bundle/'requested-tracks.jsonl')
    camera=rows(saved/'camera-frames.jsonl')
    review=rows(saved/'stand-review.jsonl')
    readback=json.loads((saved/'stand-readback.json').read_text())
    if (readback.get('review_sha256')!=sha(saved/'stand-review.jsonl') or
        not (len(request)==len(camera)==len(review)==240)):
        raise ValueError('C135709 trigger source differs')
    visible=0;maximum=0
    for i,(req,frame,review_row) in enumerate(zip(request,camera,review)):
        if (req['frame']!=frame['frame'] or req['frame']!=review_row['frame'] or
            frame['camera_frame']!=review_row['native_frame'] or
            frame['time_s']!=review_row['time_s'] or
            review_row['review_provenance']!='synthetic_cpu'):
            raise ValueError('C135709 trigger frame differs')
        if i<40 and frame['stand_sign_visible'] and frame['stand_polygon_visible']:
            visible+=1
        maximum=max(maximum,abs(review_row['reviewed_ego_y_m']-req['ego_y_m']))
    unverified=any(readback.get(k) is False for k in
        ('official_designation_verified','sign_appropriateness_verified',
         'non_taxicab_actual_use_verified','passenger_loading_exception_verified'))
    selected=('fallback1' if visible<20 else 'fallback2' if maximum>.2 else
        'fallback3' if unverified else 'primary')
    return {'format':'c135709-measured-trigger-v1',
        'case_id':measurement['case_id'],'candidate_id':measurement['candidate_id'],
        'first_40_visible_frames':visible,
        'maximum_reviewed_trajectory_deviation_m':round(maximum,6),
        'statutory_context_unverified':unverified,
        'triggered_candidate':selected,'candidate_selected_for_delivery':None,
        'source_kind':'synthetic_cpu','delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path)
    p.add_argument('--saved-dir',type=Path);a=p.parse_args()
    print(json.dumps(route(a.bundle,a.saved_dir)))
