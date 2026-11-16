"""Prove a freshly materialized exact bundle can start original capture."""
import json
import tempfile
from pathlib import Path

import capture

ROOT=Path(__file__).resolve().parent


def rejected(fn,label):
    try:fn()
    except ValueError:return label
    raise AssertionError('Capture preflight accepted '+label)


def prove():
    source=ROOT/'drafts/reference/primary'
    cfg=json.loads((source/'config.json').read_text())
    negatives=[]
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)/'attempt'
        output.mkdir()
        (output/'config.json').write_bytes((source/'config.json').read_bytes())
        capture.prepare_output(source,output,cfg)
        assert (output/'config.json').read_bytes()==(source/'config.json').read_bytes()
        (output/'native-raw-actors.jsonl').write_text('previous capture\n')
        negatives.append(rejected(lambda:capture.prepare_output(source,output,cfg),
                                  'prior-raw-capture'))
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)/'attempt';output.mkdir()
        (output/'config.json').write_text('{}\n')
        negatives.append(rejected(lambda:capture.prepare_output(source,output,cfg),
                                  'changed-materialized-config'))
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)/'fresh'
        capture.prepare_output(source,output,cfg)
        assert (output/'config.json').read_bytes()==(source/'config.json').read_bytes()
    frame=capture.frame_join_record(7,1207,.35)
    assert frame['video_frame']==7 and frame['native_frame']==frame['carla_frame']==1207
    assert frame['views']==[x[0] for x in capture.CAMERAS]
    negatives.append(rejected(lambda:capture.frame_join_record(7,'1207',.35),
                              'noninteger-native-frame'))
    negatives.append(rejected(lambda:capture.frame_join_record(7,1207,float('nan')),
                              'nonfinite-frame-time'))
    return {'format':'c146314-capture-output-proof-v1','passed':True,
            'fresh_materialized_accepted':True,'fresh_empty_accepted':True,
            'native_frame_join_names_checked':True,
            'negative_rejections':negatives,'carla_executed':False}


if __name__=='__main__':
    print(json.dumps(prove(),sort_keys=True))
