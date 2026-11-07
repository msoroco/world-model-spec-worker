"""Independent five-case saved source comparison; synthetic physical claims excluded."""
import json
import math
from pathlib import Path
import sys
import tempfile

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
sys.path.insert(0,str(FOLDER/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from geometry import TARGET_FEET
from saved_fixture_proof_import import make_base
from finalize import finalize


def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    observations={}
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c394300-independent-saved-') as temp:
        root=Path(temp)
        for suffix in TARGET_FEET:
            case=root/suffix;make_base(case,suffix)
            report=finalize(case,case/'analysis-report.json')
            result=json.loads((case/'result.json').read_text())
            samples=rows(case/'native_samples.jsonl');mapping=rows(case/'video_frames.jsonl')
            distance=report['measurements']['center_lane_entry_to_turn_distance']['value']
            first,last=distance['entry_frame_bracket'],distance['turn_onset_frame_bracket']
            e=first[1]-100;t=last[1]-100
            assert first==[samples[e-1]['native_frame'],samples[e]['native_frame']]
            assert last==[samples[t-1]['native_frame'],samples[t]['native_frame']]
            cumulative=[0.0]
            for a,b in zip(samples,samples[1:]):
                cumulative.append(cumulative[-1]+math.dist(a['native_center_xy_m'],b['native_center_xy_m']))
            lower=cumulative[t-1]-cumulative[e]
            upper=cumulative[t]-cumulative[e-1]
            observed=distance['entry_to_turn_distance_interval_m']
            assert abs(observed[0]-lower)<1e-8 and abs(observed[1]-upper)<1e-8
            assert samples[0]['native_center_xy_m']==[-95.0,3.5]
            assert samples[-1]['native_road_id']==4 and samples[-1]['native_lane_id']==-1
            assert all(m['carla_frame']==s['native_frame'] and m['time_s']==s['time_s']
                       for m,s in zip(mapping,samples))
            assert (not result['setup_confirmed'] and not result['behavior_attempted'] and
                    not result['maneuver_completed'] and not result['accepted'] and
                    result['provenance_kind']=='synthetic_local_diagnostic')
            observations[suffix]={'requested_ft':TARGET_FEET[suffix],
                'relation':distance['threshold_relation'],'distance_interval_m':observed,
                'entry_frame':first[1],'turn_frame':last[1],
                'x_trace':[s['native_center_xy_m'][0] for s in samples],
                'y_trace':[s['native_center_xy_m'][1] for s in samples]}
        reference=observations['witness_1']
        for value in observations.values():
            assert value['x_trace']==reference['x_trace']
            assert value['turn_frame']==reference['turn_frame']
            assert value['y_trace']!=reference['y_trace'] or value is reference
        assert [observations[k]['relation'] for k in TARGET_FEET]==[
            'within_200_feet','exceeds_200_feet','within_200_feet',
            'unresolved_at_200_feet','exceeds_200_feet']
        assert len({observations[k]['entry_frame'] for k in TARGET_FEET})==5
        print(json.dumps({'passed':True,'cases':5,'frames_per_case':480,
            'held':'map source, law, cell, actor, 20 Hz, 24 s, cameras, x/frame/time and turn station',
            'varied':'lane-change request and original lateral/body contact station',
            'entry_frames':{k:v['entry_frame'] for k,v in observations.items()},
            'sampled_intervals_m':{k:v['distance_interval_m'] for k,v in observations.items()},
            'physical_native_verified':False,'accepted_recordings':0}))


if __name__=='__main__':main()
