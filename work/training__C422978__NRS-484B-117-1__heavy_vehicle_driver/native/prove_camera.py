"""Exercise source-bound synthetic camera packets and fallback3 trigger decisions."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from measure_camera import camera_packet
from triggers import evaluate

HERE=Path(__file__).resolve().parent
CASES=('reference','contrast')
STATES={'clear':420,'low_visibility':300}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path,rows):
    path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def rejected(fn):
    try:
        fn()
    except (ValueError,TypeError):
        return True
    raise AssertionError('Changed camera review accepted')


def prove():
    positives,negatives=[],[]
    for case in CASES:
        saved=HERE/'saved-fixtures'/case/'fallback3'
        actors=[json.loads(line) for line in (saved/'native-observed.jsonl').read_text().splitlines()]
        mapping=[json.loads(line) for line in (saved/'video_frames.jsonl').read_text().splitlines()]
        for state,count in STATES.items():
            target=HERE/'camera-fixtures'/case/state
            target.mkdir(parents=True,exist_ok=True)
            review=target/'camera-review.jsonl'
            video=target/'sidewalk-video-stub.txt'
            video.write_text('synthetic CPU camera stub; no pixel video\n'+
                             ''.join(f'{case}/{state}/{i}\n' for i in range(480)))
            annotations=[]
            for index,(actor,frame) in enumerate(zip(actors,mapping)):
                visible=index<count
                annotations.append({'frame':index,'video_frame':index,
                                    'native_frame':actor['native_frame'],
                                    'time_s':frame['time_s'],'source_kind':'synthetic_cpu',
                                    'camera':'sidewalk','review_method':'synthetic_cpu_box',
                                    'subject_visible':visible,
                                    'subject_box_xywh':[.25,.3,.45,.35] if visible else None})
            write_rows(review,annotations)
            packet=camera_packet(saved,review,video)
            decision=evaluate(case,'fallback3',saved/'native-observed.jsonl',
                              sha(saved/'native-observed.jsonl'),packet)
            if (packet['visible_frames']!=count or decision['triggered'] != (count<360) or
                    packet['pixel_annotation_truth_verified'] or packet['physical_or_legal_acceptance']):
                raise AssertionError('Synthetic camera trigger decision differs')
            positives.append({'case':case,'state':state,'packet':packet,
                              'fallback3_triggered':decision['triggered']})
            with tempfile.TemporaryDirectory(dir=HERE) as temporary:
                altered=Path(temporary)/'review.jsonl'
                changed=[dict(row) for row in annotations]
                changed[0]['native_frame']+=1
                write_rows(altered,changed)
                negatives.append({'case':case,'state':state,'mutation':'native_join',
                                  'rejected':rejected(lambda:camera_packet(saved,altered,video))})
                changed=[dict(row) for row in annotations]
                changed[0]['review_method']='manual_box_review'
                write_rows(altered,changed)
                negatives.append({'case':case,'state':state,'mutation':'review_provenance',
                                  'rejected':rejected(lambda:camera_packet(saved,altered,video))})
                changed=[dict(row) for row in annotations]
                changed[0]['subject_box_xywh']=[.9,.3,.45,.35]
                write_rows(altered,changed)
                negatives.append({'case':case,'state':state,'mutation':'box_bounds',
                                  'rejected':rejected(lambda:camera_packet(saved,altered,video))})
                negatives.append({'case':case,'state':state,'mutation':'source_hash',
                                  'rejected':rejected(lambda:camera_packet(saved,altered,video,packet['source_hashes']))})
    proof={'format':'c422978-heavy-camera-cpu-proof-v1',
           'camera_processor_sha256':sha(HERE/'measure_camera.py'),
           'positives':positives,'negatives':negatives,
           'original_native_observed':False,'pixel_annotation_truth_verified':False,
           'delivery_ready':False}
    (HERE/'camera-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    result=prove()
    print(json.dumps({'positives':len(result['positives']),
                      'negatives':len(result['negatives'])}))
