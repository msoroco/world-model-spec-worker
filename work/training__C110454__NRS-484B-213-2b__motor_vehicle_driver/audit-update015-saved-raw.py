"""Recompute the intersection saved diagnostic from 480 retained raw rows."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from finalize import finalize

spec=importlib.util.spec_from_file_location('c110454_saved_fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='c110454-update015-raw-audit-') as temp:
        root=Path(temp);positive=root/'positive';fixture.make_base(positive,'reference',480)
        channel=positive/'channels/kin.position.jsonl';channel.parent.mkdir(exist_ok=True)
        channel.write_text('{"time_s":0.05,"value":"stale fixture channel"}\n')
        negative=root/'missing';shutil.copytree(positive,negative)
        provenance=root/'bad-speed';shutil.copytree(positive,provenance)
        (negative/'native_samples.jsonl').unlink()
        trace=rows(provenance/'trace.jsonl');trace[0]['speed_provenance']='original_trace_actor_get_velocity'
        (provenance/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
        report=finalize(positive,positive/'analysis-report.json')
        result=json.loads((positive/'result.json').read_text())
        motion=rows(positive/'native_samples.jsonl')
        mapping=rows(positive/'video_frames.jsonl')
        names=[item['name'] for item in result['recording_evidence'] if item['reference'].startswith('channels/')]
        assert len(names)==11 and report['original_joins']['frames']==480
        channels={name:rows(positive/'channels'/(name+'.jsonl')) for name in names}
        for index,(sample,frame) in enumerate(zip(motion,mapping)):
            assert sample['native_frame']==frame['native_frame']
            for channel_rows in channels.values():
                assert len(channel_rows)==480 and abs(channel_rows[index]['time_s']-frame['time_s'])<1e-4
            assert channels['kin.position'][index]['value']==sample['native_center_xy_m']
            assert channels['rel.occupies'][index]['value']==sample['native_body_xy_m']
            assert channels['camera_frame_join'][index]['value']==frame
            assert channels['native_body_pose_control'][index]['value']==sample
        assert channels['kin.position'][0]['value']!='stale fixture channel'
        assert result['provenance_kind']=='synthetic_local_diagnostic'
        assert result['setup_confirmed'] is False and result['behavior_attempted'] is False
        assert result['maneuver_completed'] is False and result['accepted'] is False
        negatives=0
        for attempt,needle in ((negative,'native_samples.jsonl'),
                               (provenance,'Synthetic speed must retain diagnostic provenance')):
            try:finalize(attempt,attempt/'analysis-report.json')
            except (ValueError,KeyError) as error:
                assert needle in str(error)
                negatives+=1
            else:raise ValueError('Damaged raw source accepted')
    return {'frames':480,'derived_channels':11,'raw_channel_joins_checked':5280,
            'isolated_negative_rejections':negatives,'selected':False,
            'physical_behavior_claimed':False}


if __name__=='__main__':
    print(json.dumps(audit(),sort_keys=True))
