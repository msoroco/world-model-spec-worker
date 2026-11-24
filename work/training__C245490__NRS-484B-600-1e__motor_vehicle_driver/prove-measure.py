"""Synthetic source-shaped speed/lane proof, not original CARLA motion."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c245490-measure-fixtures'
SCRATCH.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(HERE/'native'))
from measure import measure


def fixture(name,speed):
    path=SCRATCH/(name+'.jsonl')
    with path.open('w') as out:
        for i in range(600):
            out.write(json.dumps({'video_frame':i,'native_frame':1000+i,
                'time_s':i/20,'subject_id':42,'lane_id':-1 if i<300 else -2,
                'velocity_xyz_mps':[speed,0,0],
                'provenance':'synthetic_native_sample'})+'\n')
    return path


def reject(path,expected):
    try:measure(path)
    except ValueError as exc:
        assert expected in str(exc)
        return str(exc)
    raise AssertionError('corrupt original source accepted')


def main():
    above=fixture('above',36.5);below=fixture('below',33.5)
    a,b=measure(above),measure(below)
    assert a['samples_above_80_mph']==600 and b['samples_above_80_mph']==0
    assert a['first_destination_lane_frame']==300 and b['first_destination_lane_frame']==300
    lines=above.read_text().splitlines()
    missing=SCRATCH/'missing-frame.jsonl';missing.write_text('\n'.join(lines[:-1])+'\n')
    neg_frame=reject(missing,'missing original 600-frame')
    broken=[json.loads(line) for line in lines]
    del broken[100]['velocity_xyz_mps']
    invalid_velocity=SCRATCH/'missing-velocity.jsonl'
    invalid_velocity.write_text(''.join(json.dumps(row)+'\n' for row in broken))
    neg_velocity=reject(invalid_velocity,'original velocity vector missing')
    broken=[json.loads(line) for line in lines]
    broken[100]['lane_id']=-3
    invalid_lane=SCRATCH/'invalid-lane.jsonl'
    invalid_lane.write_text(''.join(json.dumps(row)+'\n' for row in broken))
    neg_lane=reject(invalid_lane,'original lane readback missing')
    print(json.dumps({'passed':True,'fixture_kind':'synthetic_native_sample',
        'above':{'max_mph':a['maximum_mph'],'samples_above_80':a['samples_above_80_mph'],
                 'destination_lane_frame':a['first_destination_lane_frame']},
        'below':{'max_mph':b['maximum_mph'],'samples_above_80':b['samples_above_80_mph']},
        'negative_missing_frame':neg_frame,'negative_missing_velocity':neg_velocity,
        'negative_invalid_lane':neg_lane,
        'measure_sha256':hashlib.sha256((HERE/'native/measure.py').read_bytes()).hexdigest()},
        sort_keys=True))

if __name__=='__main__':main()
