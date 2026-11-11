"""Check two traversal raw diagnostics and damaged-source rejection."""
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
base_spec=importlib.util.spec_from_file_location('finalize_base',HERE/'native/finalize.py')
base=importlib.util.module_from_spec(base_spec)
sys.modules['finalize_base']=base
base_spec.loader.exec_module(base)
from finalize_traversal import finalize


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    root=REPO/'.runtime-work/c110454-update015-traversal-raw'
    left_counts={};joined=0
    for suffix in ('traversal_reference','traversal_contrast'):
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
            i=sample['video_frame']
            assert sample['native_frame']==frame['native_frame']
            assert sample['speed_provenance']=='synthetic_native_sample'
            assert all(len(channel)==480 for channel in channels.values())
            assert channels['kin.position'][i]['value']==sample['native_center_xy_m']
            assert channels['rel.occupies'][i]['value']==sample['native_body_xy_m']
            assert channels['camera_frame_join'][i]['value']==frame
            assert channels['native_body_pose_control'][i]['value']==sample
            joined+=11
        left_counts[suffix]=result['measured_values']['moving_left_traversal_frames']
    assert left_counts=={'traversal_reference':0,'traversal_contrast':39}
    rejected=0
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='c110454-trav-negative-') as temp:
        for kind in ('missing_motion','false_speed'):
            attempt=Path(temp)/kind
            shutil.copytree(root/'traversal_reference',attempt)
            (attempt/'result.json').unlink();(attempt/'analysis-report.json').unlink()
            if kind=='missing_motion':(attempt/'native_samples.jsonl').unlink()
            else:
                trace=rows(attempt/'trace.jsonl')
                trace[0]['speed_provenance']='original_trace_actor_get_velocity'
                (attempt/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
            try:finalize(attempt,attempt/'analysis-report.json')
            except (ValueError,KeyError):rejected+=1
            else:raise ValueError('Damaged traversal source accepted')
    return {'cases':2,'raw_channel_joins_checked':joined,
            'moving_left_counts':left_counts,'isolated_negative_rejections':rejected,
            'selected':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
