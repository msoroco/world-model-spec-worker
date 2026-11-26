"""Exercise saved analysis and missing-source rejection without CARLA."""
import json
import os
from pathlib import Path
import tempfile

from finalize import finalize
from prove_lane_arrow import packet

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent


def put_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))


def prepare(root):
    construction=json.loads((ROOT/'draft-same_lane/construction.json').read_text())
    cfg=next(json.loads(f['content']) for f in construction['files'] if f['path']=='config.json')
    (root/'config.json').write_text(json.dumps(cfg)+'\n')
    (root/'native-map-readback.xodr').write_text((HERE/'road.xodr').read_text())
    signals=packet()['frames']
    for row in signals:
        row['diagnostic_fixture']=True
        row['signal']['mount_m']=[60.0,-1.75,4.5]
    put_rows(root/'native-signal-rows.jsonl',signals)
    frames=[]
    trace=[]
    evidence=[]
    for i,row in enumerate(signals):
        native=row['native_frame']
        frames.append({'native_frame':native,'carla_frame':native,
            'camera_native_frames':{name:native for name in ('overview','approach','reference_corner','driver_reference')}})
        trace.append({'frame':native,'position_m':[10+i*75/599,-1.75,0.0]})
        evidence.append({'original_frame':native})
    put_rows(root/'video_frames.jsonl',frames)
    put_rows(root/'trace.jsonl',trace)
    put_rows(root/'capture/evidence.jsonl',evidence)
    for name in ('overview','approach','reference_corner','driver_reference'):
        (root/(name+'.mkv')).write_text('fixture placeholder; no video decode claim\n')


def main():
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temp:
        root=Path(temp)/'positive'
        root.mkdir()
        prepare(root)
        report=finalize(root,root/'analysis.json')
        result=json.loads((root/'result.json').read_text())
        assert report['measurements']['facing_downward_arrow_frames']['value']==600
        assert result['maneuver_completed'] is False and result['accepted'] is False
        assert result['target_checks'][0]['matched'] is True
        negative=Path(temp)/'negative'
        negative.mkdir()
        prepare(negative)
        (negative/'native-signal-rows.jsonl').unlink()
        try:
            finalize(negative,negative/'analysis.json')
        except ValueError as exc:
            assert 'native-signal-rows.jsonl' in str(exc)
        else:
            raise AssertionError('accepted absent original signal source')
        missing_frame=Path(temp)/'missing-frame'
        missing_frame.mkdir()
        prepare(missing_frame)
        rows=[json.loads(line) for line in (missing_frame/'video_frames.jsonl').read_text().splitlines()]
        rows[200]['camera_native_frames'].pop('reference_corner')
        put_rows(missing_frame/'video_frames.jsonl',rows)
        try:
            finalize(missing_frame,missing_frame/'analysis.json')
        except ValueError as exc:
            assert 'frame join' in str(exc)
        else:
            raise AssertionError('accepted absent original camera frame')
        print(json.dumps({'passed':True,'positive_frames':600,
            'negative_missing_original_signal':True,
            'negative_missing_camera_frame':True,
            'physical_or_legal_acceptance_claimed':False},sort_keys=True))


if __name__=='__main__':
    main()
