"""CPU source-shape proofs for three separate C404492 statutory alternatives."""
import json
import os
from pathlib import Path
import tempfile

from measure_emergency import measure
from prove_emergency import fixture


def rewrite(path,change):
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        change(row)
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def reject(root,branch):
    try:
        measure(root,branch=branch)
    except ValueError:
        return
    raise AssertionError('Unproved statutory branch accepted: '+branch)


def context(root,**changes):
    path=root/'emergency_context.json'
    value=json.loads(path.read_text())
    value.update(changes)
    path.write_text(json.dumps(value)+'\n')


def main():
    with tempfile.TemporaryDirectory(prefix='c404492-alternatives-',dir=os.environ['TMPDIR']) as temp:
        base=Path(temp)
        official_behind=base/'official_behind';fixture(official_behind,False)
        official=base/'official_abreast';fixture(official,True)
        for location in (official_behind,official):
            context(location,emergency_vehicle_authorized=False,
                    official_regulatory_vehicle=True,
                    regulatory_agency_vehicle_source='synthetic-fixture:reviewed-agency-source')
        official_follow=measure(official_behind,branch='regulatory_moving')
        official_result=measure(official,branch='regulatory_moving')
        assert official_result['statutory_branch']=='regulatory_moving'
        assert official_result['legal_result'] is None
        assert sum(r['longitudinal_overlap_length_m']>0 for r in official_follow['per_frame_geometry'])==0
        assert sum(r['longitudinal_overlap_length_m']>0 for r in official_result['per_frame_geometry'])==299
        reject(official,'emergency_moving')
        context(official,official_regulatory_vehicle=False)
        reject(official,'regulatory_moving')

        movement=base/'movement';fixture(movement,True)
        context(movement,preparing_to_move_reviewed=True,
                preparing_to_move_source='synthetic-fixture:independent-preparation-review',
                visible_vehicle_movement_source='synthetic-fixture:four-camera-motion-review')
        def moving_pose(row):
            row['emergency']['visible_vehicle_movement']=100<=row['video_frame']<140
        rewrite(movement/'vehicle_poses.jsonl',moving_pose)
        movement_result=measure(movement,branch='emergency_preparing_movement')
        assert movement_result['visible_preparation_frames']==40
        assert movement_result['legal_result'] is None
        context(movement,visible_vehicle_movement_source=None)
        reject(movement,'emergency_preparing_movement')

        signal=base/'hand_signal';fixture(signal,True)
        context(signal,preparing_to_move_reviewed=True,
                preparing_to_move_source='synthetic-fixture:independent-preparation-review',
                driver_hand_signal_visual_source='synthetic-fixture:driver-and-camera-review')
        def signaled_pose(row):
            row['emergency']['speed_mps']=0
            row['emergency']['driver_hand_signal_visible']=100<=row['video_frame']<140
        rewrite(signal/'vehicle_poses.jsonl',signaled_pose)
        signal_result=measure(signal,branch='emergency_preparing_hand_signal')
        assert signal_result['visible_preparation_frames']==40
        assert signal_result['legal_result'] is None
        reject(signal,'emergency_moving')
        rewrite(signal/'vehicle_poses.jsonl',lambda row:row['emergency'].update(driver_hand_signal_visible=False))
        reject(signal,'emergency_preparing_hand_signal')
        print(json.dumps({'regulatory_moving_source_shape_passed':True,
                          'regulatory_follow_overlap_frames':0,
                          'regulatory_abreast_overlap_frames':299,
                          'visible_movement_frames':40,'driver_hand_signal_frames':40,
                          'negative_source_checks':5,'original_native_executed':False,
                          'legal_result':None},sort_keys=True))


if __name__=='__main__':main()
