"""Independently recompute C135709 measured fallback signal variants."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def audit():
    path=CASE/'native/trigger-proof.json';proof=json.loads(path.read_text())
    if (proof['format']!='c135709-trigger-proof-v1' or
        proof['baseline']['triggered_candidate']!='fallback3' or
        len(proof['variants'])!=2 or proof['changed_frame_rejected'] is not True or
        proof['candidate_selected_for_delivery'] is not None or proof['delivery_ready']):
        raise ValueError('C135709 trigger proof differs')
    seen=set();checked=0
    for variant in proof['variants']:
        name=variant['name']
        if name not in ('entry_occluded','pose_deviation') or name in seen:
            raise ValueError('C135709 trigger variants differ')
        seen.add(name);folder=CASE/'native/trigger-fixtures'/name
        if variant['source_hashes']!={p.name:sha(p) for p in folder.iterdir() if p.is_file()}:
            raise ValueError('C135709 trigger fixture hash differs')
        camera=rows(folder/'camera-frames.jsonl')
        review=rows(folder/'stand-review.jsonl')
        request=rows(CASE/'offline/bundles/reference/primary/requested-tracks.jsonl')
        readback=json.loads((folder/'stand-readback.json').read_text())
        if (not (len(camera)==len(review)==len(request)==240) or
            readback['review_sha256']!=sha(folder/'stand-review.jsonl')):
            raise ValueError('C135709 trigger fixture join differs')
        visible=sum(x['stand_sign_visible'] and x['stand_polygon_visible']
                    for x in camera[:40])
        deviation=max(abs(a['reviewed_ego_y_m']-b['ego_y_m'])
                      for a,b in zip(review,request))
        expected='fallback1' if visible<20 else 'fallback2' if deviation>.2 else 'fallback3'
        measured=variant['measurement']
        if (variant['triggered_candidate']!=expected or
            measured['triggered_candidate']!=expected or
            measured['first_40_visible_frames']!=visible or
            abs(measured['maximum_reviewed_trajectory_deviation_m']-deviation)>1e-6 or
            measured['delivery_ready']):
            raise ValueError('C135709 measured trigger differs')
        checked+=240
    receipt={'format':'c135709-independent-trigger-audit-v1',
        'proof_sha256':sha(path),'saved_rows_recomputed':checked,
        'positive_trigger_variants':len(seen),
        'negative_joins_rejected':1,'delivery_ready':False}
    (CASE/'native/trigger-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':print(json.dumps(audit()))
