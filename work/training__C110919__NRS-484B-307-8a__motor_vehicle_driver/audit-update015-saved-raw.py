"""Independently check raw-derived right-turn channels and damaged sources."""
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


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    root=REPO/'.runtime-work/c110919-update015-saved-raw'
    stops={};joined=0
    for suffix in ('reference','contrast'):
        attempt=root/suffix
        result=json.loads((attempt/'result.json').read_text())
        report=json.loads((attempt/'analysis-report.json').read_text())
        samples=rows(attempt/'native_samples.jsonl')
        frames=rows(attempt/'video_frames.jsonl')
        channels={item['name']:rows(attempt/item['reference']) for item in result['recording_evidence']}
        assert len(channels)==10 and len(samples)==len(frames)==480
        assert report['original_joins']['frames']==480
        assert result['provenance_kind']=='synthetic_local_diagnostic'
        assert result['setup_confirmed'] is False and result['behavior_attempted'] is False
        assert result['maneuver_completed'] is False and result['accepted'] is False
        for sample,frame in zip(samples,frames):
            i=frame['video_frame']
            assert sample['native_frame']==frame['native_frame']
            assert sample['speed_provenance']=='synthetic_native_sample'
            assert all(len(channel)==480 for channel in channels.values())
            assert channels['kin.velocity'][i]['value']==sample['speed_mps']
            assert channels['native_body_pose_control'][i]['value']==sample
            assert channels['camera_frame_join'][i]['value']==frame
            assert channels['drv.yields_to'][i]['value']['conflict_occupied']==sample['walker_conflict_occupied']
            joined+=10
        stops[suffix]=result['measured_values']['stop']['stationary_pre_crossing_frames']
    assert stops=={'reference':30,'contrast':0}
    rejected=0
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='c110919-raw-negative-') as temp:
        for kind in ('missing_geometry','false_speed'):
            attempt=Path(temp)/kind
            shutil.copytree(root/'reference',attempt)
            (attempt/'result.json').unlink();(attempt/'analysis-report.json').unlink()
            if kind=='missing_geometry':(attempt/'road_geometry.json').unlink()
            else:
                trace=rows(attempt/'trace.jsonl')
                trace[0]['speed_provenance']='original_trace_actor_get_velocity'
                (attempt/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
            try:finalize(attempt,attempt/'analysis-report.json')
            except (ValueError,KeyError):rejected+=1
            else:raise ValueError('Damaged right-turn source accepted')
    return {'cases':2,'raw_channel_joins_checked':joined,
            'stationary_pre_crossing_frames':stops,
            'isolated_negative_rejections':rejected,'selected':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
