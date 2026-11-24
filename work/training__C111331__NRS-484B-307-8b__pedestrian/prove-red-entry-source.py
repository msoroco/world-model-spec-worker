"""Construct full-duration facing-red entry/no-entry diagnostic source pair."""
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from red_entry import measure, requested, sha


def put(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def rejected(path, context):
    try:
        measure(path, context)
    except ValueError as error:
        return str(error)
    raise AssertionError('Damaged red-entry source accepted')


def main():
    folder = HERE / 'diagnostic-red-entry'
    folder.mkdir(exist_ok=True)
    scene = {'context_id': 'c111331-facing-red-v1', 'cell_id': 'C111331',
             'highway_y_max_m': 2.0, 'signal_id': 'head_ped_1',
             'signal_location_xy_m': [0.0, 5.0],
             'signal_face_vector_xy': [0.0, -1.0],
             'pedestrian_approach_vector_xy': [0.0, -1.0],
             'signal_authority_native_verified': False,
             'other_device_authority_native_verified': False,
             'original_native_observed': False}
    context = folder / 'context.json'
    context.write_text(json.dumps(scene, indent=2) + '\n')
    records = []
    sources = []
    for condition in ('condition_a','condition_b'):
        rows = requested(condition)
        target = folder / (condition + '.jsonl')
        put(target, rows)
        records.append(measure(target, context))
        sources.append(rows)
    left,right = sources
    fixed = set(left[0]) - {'pedestrian_center_xy_m','pedestrian_footprint_xy_m','requested_entry_condition'}
    if any({k:a[k] for k in fixed} != {k:b[k] for k in fixed}
           for a,b in zip(left,right)):
        raise AssertionError('Red-entry comparison changed fixed fields')
    negatives=[]
    temp=folder/'negative.jsonl'
    for name,mutate in (
        ('missing_frame',lambda rows:rows.pop()),
        ('green_signal',lambda rows:rows[220].__setitem__('signal_state','green')),
        ('other_device_permit',lambda rows:rows[220].__setitem__('other_device_permits',True)),
        ('changed_governing_head',lambda rows:rows[220].__setitem__('signal_id','vehicle_head_other_approach')),
        ('mixed_condition',lambda rows:rows[220].__setitem__('requested_entry_condition','condition_b')),
    ):
        rows=copy.deepcopy(left)
        mutate(rows)
        put(temp,rows)
        negatives.append({'mutation':name,'rejection':rejected(temp,context)})
    temp.unlink()
    bad=folder/'bad-context.json'
    bad.write_text(json.dumps(dict(scene,signal_face_vector_xy=[0.0,1.0]))+'\n')
    negatives.append({'mutation':'opposite_facing_head','rejection':rejected(folder/'condition_a.jsonl',bad)})
    bad.unlink()
    proof={'format':'c111331-red-entry-source-proof-v1','passed':True,
           'frames_per_condition':600,'rate_hz':20,'duration_s':30,
           'controlled_variable':'pedestrian_highway_entry',
           'records':records,'negative_rejections':negatives,
           'other_device_exception_tested':False,
           'physical_signal_authority_claimed':False,'legal_verdict_claimed':False}
    target=HERE/'red-entry-source-proof.json'
    target.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'passed':True,'proof_sha256':sha(target),
                      'first_entry_frame':records[1]['first_highway_footprint_frame'],
                      'negative_count':len(negatives)}))


if __name__=='__main__':
    main()
