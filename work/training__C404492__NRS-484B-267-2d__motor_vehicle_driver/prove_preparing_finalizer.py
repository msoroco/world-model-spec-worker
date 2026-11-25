"""Source-shaped diagnostic for the visible vehicle-movement branch."""
import json
import os
from pathlib import Path
import tempfile

from finalize import AID, finalize
from measure_emergency import measure
from prove_emergency import fixture


CASE=AID+'__preparing_movement'


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))


def setup(root):
    fixture(root, False)
    context_path=root/'emergency_context.json'
    context=json.loads(context_path.read_text())
    context.update(case_id=CASE, preparing_to_move_reviewed=True,
                   preparing_to_move_source='synthetic:independent-visible-preparation-review',
                   visible_vehicle_movement_source='synthetic:source-vehicle-motion-review')
    context_path.write_text(json.dumps(context, sort_keys=True)+'\n')
    poses=[json.loads(line) for line in (root/'vehicle_poses.jsonl').read_text().splitlines()]
    traces=[json.loads(line) for line in (root/'trace.jsonl').read_text().splitlines()]
    x=0.0
    for frame,(pose,trace) in enumerate(zip(poses,traces)):
        speed=0.0 if frame<80 else 0.5 if frame<120 else 4.0
        if frame:x+=speed*0.05
        emergency=pose['emergency']
        emergency['x_m']=x
        emergency['speed_mps']=speed
        emergency['visible_vehicle_movement']=80<=frame<120
        ego=pose['ego']
        ego['x_m']=x-20.0
        ego['speed_mps']=speed
        trace['position_m'][0]=ego['x_m']
        trace['speed_mps']=speed
    write_jsonl(root/'vehicle_poses.jsonl',poses)
    write_jsonl(root/'trace.jsonl',traces)


def reject(root):
    try:
        measure(root, branch='emergency_preparing_movement')
    except ValueError:
        return
    raise AssertionError('Unproved visible preparation accepted')


def main():
    with tempfile.TemporaryDirectory(prefix='c404492-preparing-finalizer-',dir=os.environ['TMPDIR']) as temp:
        parent=Path(temp)
        positive=parent/'positive'
        setup(positive)
        measured=measure(positive, branch='emergency_preparing_movement')
        if measured['samples']!=600 or measured['visible_preparation_frames']!=40:
            raise ValueError('Expected visible movement phase was not measured')
        output=parent/'report.json'
        finalize(positive, CASE, output, diagnostic=True)
        report=json.loads(output.read_text())
        if report['statutory_branch']!='emergency_preparing_movement' or report['legal_result'] is not None:
            raise ValueError('Source-shaped report claimed the wrong branch or verdict')
        negatives=(('missing-preparation-source', {'preparing_to_move_source':None}),
                   ('missing-visual-source', {'visible_vehicle_movement_source':None}),
                   ('false-review', {'preparing_to_move_reviewed':False}))
        for name,changes in negatives:
            root=parent/name
            setup(root)
            path=root/'emergency_context.json'
            context=json.loads(path.read_text())
            context.update(changes)
            path.write_text(json.dumps(context, sort_keys=True)+'\n')
            reject(root)
        absent=parent/'absent-motion'
        setup(absent)
        path=absent/'vehicle_poses.jsonl'
        poses=[json.loads(line) for line in path.read_text().splitlines()]
        for pose in poses:pose['emergency']['visible_vehicle_movement']=False
        write_jsonl(path,poses)
        reject(absent)
        print(json.dumps({'format':'c404492-preparing-finalizer-source-shape-v1',
                          'case_id':CASE,'samples':600,'visible_preparation_frames':40,
                          'negative_checks':4,'original_native_executed':False,
                          'legal_acceptance_claimed':False},sort_keys=True))


if __name__=='__main__':main()
