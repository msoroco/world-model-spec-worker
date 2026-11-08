"""Independently audit synthetic camera joins, source bytes and trigger outcomes."""
import hashlib
import json
from pathlib import Path
import tempfile

from measure_camera import camera_packet

HERE=Path(__file__).resolve().parent
CASES=('reference','contrast')
STATES={'clear':420,'low_visibility':300}
MUTATIONS=('native_join','review_provenance','box_bounds','source_hash')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def rejected(fn):
    try:
        fn()
    except (ValueError,TypeError):
        return True
    raise ValueError('Camera negative accepted')


def audit():
    path=HERE/'camera-proof.json'
    proof=json.loads(path.read_text())
    if (proof['format']!='c422978-heavy-camera-cpu-proof-v1' or
            proof['camera_processor_sha256']!=sha(HERE/'measure_camera.py') or
            len(proof['positives'])!=4 or len(proof['negatives'])!=16 or
            proof['original_native_observed'] or proof['pixel_annotation_truth_verified'] or
            proof['delivery_ready']):
        raise ValueError('Camera proof scope differs')
    seen,rows_recomputed,negatives= set(),0,0
    for positive in proof['positives']:
        case,state=positive['case'],positive['state']
        if case not in CASES or state not in STATES or (case,state) in seen:
            raise ValueError('Camera case/state identity differs')
        seen.add((case,state))
        folder=HERE/'camera-fixtures'/case/state
        saved=HERE/'saved-fixtures'/case/'fallback3'
        review=folder/'camera-review.jsonl'
        video=folder/'sidewalk-video-stub.txt'
        annotations=lines(review)
        actors=lines(saved/'native-observed.jsonl')
        mapping=lines(saved/'video_frames.jsonl')
        if len(annotations)!=480 or len(actors)!=480 or len(mapping)!=480:
            raise ValueError('Camera fixture rows differ')
        visible=0
        for index,(row,actor,frame) in enumerate(zip(annotations,actors,mapping)):
            if (row['frame']!=index or row['video_frame']!=index or
                    row['native_frame']!=actor['native_frame'] or
                    row['time_s']!=frame['time_s'] or
                    row['source_kind']!='synthetic_cpu' or row['camera']!='sidewalk' or
                    row['review_method']!='synthetic_cpu_box'):
                raise ValueError('Camera annotation/frame join differs')
            if row['subject_visible']:
                if row['subject_box_xywh']!=[.25,.3,.45,.35]:
                    raise ValueError('Synthetic camera box differs')
                visible+=1
            elif row['subject_box_xywh'] is not None:
                raise ValueError('Invisible camera body has box')
            rows_recomputed+=1
        packet=positive['packet']
        if (visible!=STATES[state] or packet['visible_frames']!=visible or
                packet['visible_fraction']!=visible/480 or
                packet['source_hashes']!={'review_sha256':sha(review),'video_sha256':sha(video),
                                           'actor_sha256':sha(saved/'native-observed.jsonl'),
                                           'video_mapping_sha256':sha(saved/'video_frames.jsonl')} or
                packet!=camera_packet(saved,review,video,packet['source_hashes']) or
                positive['fallback3_triggered']!=(visible<360)):
            raise ValueError('Camera packet or fallback3 threshold differs')
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            altered=Path(temporary)/'review.jsonl'
            for mutation in MUTATIONS:
                changed=[dict(row) for row in annotations]
                if mutation=='native_join': changed[0]['native_frame']+=1
                elif mutation=='review_provenance': changed[0]['review_method']='manual_box_review'
                else: changed[0]['subject_box_xywh']=[.9,.3,.45,.35]
                altered.write_text(''.join(json.dumps(row)+'\n' for row in changed))
                if mutation=='source_hash':
                    rejected(lambda:camera_packet(saved,altered,video,packet['source_hashes']))
                else:
                    rejected(lambda:camera_packet(saved,altered,video))
                negatives+=1
    if seen!={(case,state) for case in CASES for state in STATES} or \
            {(n['case'],n['state'],n['mutation']) for n in proof['negatives']} != {
                (case,state,mutation) for case,state in seen for mutation in MUTATIONS} or \
            not all(n['rejected'] is True for n in proof['negatives']):
        raise ValueError('Camera negative coverage differs')
    result={'format':'c422978-heavy-independent-camera-audit-v1',
            'proof_sha256':sha(path),'positive_packets':len(seen),
            'annotation_rows_recomputed':rows_recomputed,
            'negative_rejections_reproduced':negatives,
            'original_native_observed':False,'delivery_ready':False}
    (HERE/'camera-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    result=audit()
    print(json.dumps({'positives':result['positive_packets'],
                      'rows':result['annotation_rows_recomputed'],
                      'negatives':result['negative_rejections_reproduced']}))
