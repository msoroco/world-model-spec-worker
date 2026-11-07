"""Independent three-case saved interval audit; synthetic evidence only."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from geometry import TARGET_FEET
from finalize import finalize

spec=importlib.util.spec_from_file_location('saved_fixture_proof',HERE/'saved-fixture-proof.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    observations={}
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c394300-3c-independent-saved-') as temp:
        root=Path(temp)
        for suffix in TARGET_FEET:
            case=root/suffix;module.make_base(case,suffix)
            report=finalize(case,case/'analysis-report.json')
            result=json.loads((case/'result.json').read_text())
            samples=rows(case/'native_samples.jsonl');mapping=rows(case/'video_frames.jsonl')
            measured=report['measurements']['after_left_turn_distance_interval']['value']
            transition=measured['left_turn_road_transition_frame_bracket']
            completion=measured['turn_completion_frame_bracket']
            merge=measured['merge_onset_frame_bracket']
            c=completion[1]-100;m=merge[1]-100
            assert transition[1]<completion[1]<merge[1]<measured['full_merge_native_frame']
            assert completion==[samples[c-1]['native_frame'],samples[c]['native_frame']]
            assert merge==[samples[m-1]['native_frame'],samples[m]['native_frame']]
            cumulative=[0.0]
            for a,b in zip(samples,samples[1:]):
                cumulative.append(cumulative[-1]+math.dist(a['native_center_xy_m'],b['native_center_xy_m']))
            lower=cumulative[m-1]-cumulative[c]
            upper=cumulative[m]-cumulative[c-1]
            observed=measured['distance_interval_m']
            assert math.isclose(observed[0],lower,abs_tol=1e-8)
            assert math.isclose(observed[1],upper,abs_tol=1e-8)
            assert samples[0]['native_road_id']==4 and samples[0]['native_lane_id']==-1
            assert samples[-1]['native_road_id']==1 and samples[-1]['native_lane_id']==-2
            assert all(maprow['carla_frame']==sample['native_frame'] and maprow['time_s']==sample['time_s']
                       for maprow,sample in zip(mapping,samples))
            assert report['acquisition_provenance']['native_executed'] is False
            assert result['provenance_kind']=='synthetic_local_diagnostic'
            assert result['setup_confirmed'] is False
            assert result['behavior_attempted'] is False
            assert result['maneuver_completed'] is False
            assert result['accepted'] is False
            observations[suffix]={'requested_ft':TARGET_FEET[suffix],
                'relation':measured['threshold_relation'],'interval_m':observed,
                'turn_completion_frame':completion[1],'merge_onset_frame':merge[1],
                'x_trace':[sample['native_center_xy_m'][0] for sample in samples],
                'y_trace':[sample['native_center_xy_m'][1] for sample in samples],
                'frame_trace':[sample['native_frame'] for sample in samples],
                'time_trace':[sample['time_s'] for sample in samples]}
        first=observations['below_50_ft']
        for value in observations.values():
            assert value['x_trace']==first['x_trace']
            assert value['frame_trace']==first['frame_trace']
            assert value['time_trace']==first['time_trace']
            assert value['turn_completion_frame']==first['turn_completion_frame']
        assert [observations[k]['relation'] for k in TARGET_FEET]==[
            'within_50_feet','unresolved_at_50_feet','exceeds_50_feet']
        assert len({observations[k]['merge_onset_frame'] for k in TARGET_FEET})==3
        print(json.dumps({'passed':True,'cases':3,'frames_per_case':480,
            'held':'map source, law, cell, actor, 20 Hz, 24 s, cameras, x/frame/time and turn completion',
            'varied':'merge station and original lateral/body through-lane contact',
            'merge_onset_frames':{k:v['merge_onset_frame'] for k,v in observations.items()},
            'sampled_intervals_m':{k:v['interval_m'] for k,v in observations.items()},
            'physical_native_verified':False,'accepted_recordings':0}))


if __name__=='__main__':audit()
