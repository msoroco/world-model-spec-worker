"""Check four raw statutory diagnostics and damaged-source rejection."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from finalize_statutory import finalize


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    root=REPO/'.runtime-work/c110454-update015-statutory-raw'
    relations={};joined=0
    for suffix in ('rail_reference','rail_contrast','oneway_absent','oneway_present'):
        attempt=root/suffix
        result=json.loads((attempt/'result.json').read_text())
        report=json.loads((attempt/'analysis-report.json').read_text())
        samples=rows(attempt/'native_samples.jsonl')
        frames=rows(attempt/'video_frames.jsonl')
        channels={item['name']:rows(attempt/item['reference']) for item in result['recording_evidence']
                  if item['reference'].startswith('channels/')}
        assert len(channels)==11 and len(samples)==len(frames)==480
        assert report['original_joins']['frames']==480
        assert result['provenance_kind']=='synthetic_local_diagnostic'
        assert result['setup_confirmed'] is False and result['behavior_attempted'] is False
        assert result['maneuver_completed'] is False and result['accepted'] is False
        for sample,frame in zip(samples,frames):
            assert sample['native_frame']==frame['native_frame']
            assert sample['speed_provenance']=='synthetic_native_sample'
            assert all(len(channel)==480 for channel in channels.values())
            i=sample['video_frame']
            assert channels['kin.position'][i]['value']==sample['native_center_xy_m']
            assert channels['rel.occupies'][i]['value']==sample['native_body_xy_m']
            assert channels['camera_frame_join'][i]['value']==frame
            assert channels['native_body_pose_control'][i]['value']==sample
            joined+=11
        relations[suffix]=result['measured_values']['sampled_relation']
    assert relations=={'rail_reference':'outside_100_ft','rail_contrast':'within_100_ft',
                       'oneway_absent':'within_100_ft','oneway_present':'within_100_ft'}
    rejected=0
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='c110454-statutory-negative-') as temp:
        for kind in ('missing_motion','false_speed'):
            attempt=Path(temp)/kind
            shutil.copytree(root/'rail_reference',attempt)
            (attempt/'result.json').unlink();(attempt/'analysis-report.json').unlink()
            if kind=='missing_motion':(attempt/'native_samples.jsonl').unlink()
            else:
                trace=rows(attempt/'trace.jsonl')
                trace[0]['speed_provenance']='original_trace_actor_get_velocity'
                (attempt/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
            try:finalize(attempt,attempt/'analysis-report.json')
            except (ValueError,KeyError):rejected+=1
            else:raise ValueError('Damaged statutory source accepted')
    return {'cases':4,'raw_channel_joins_checked':joined,
            'isolated_negative_rejections':rejected,'selected':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
