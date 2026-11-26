"""Synthetic bridge source-shaped tests; not administrative or CARLA evidence."""
import hashlib,json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c32014-measure-fixtures'
SCRATCH.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(HERE/'native'))
from measure import measure


def fixture(label,speed):
    folder=SCRATCH/label;folder.mkdir(exist_ok=True)
    context=folder/'bridge-context.json';history=folder/'bridge-speed-history.jsonl'
    context.write_text(json.dumps({'bridge_x_m':[0.0,100.0],'sign_limit_mph':25.0,
       'posting_distance_m':30.48,
       'native_bridge_survey':[{'x':0},{'x':50},{'x':100}],
       'native_sign_survey':[{'id':'101'},{'id':'102'}],
       'fixture_only':True})+'\n')
    with history.open('w') as out:
        for i in range(600):
            x=-70+i*speed/20
            out.write(json.dumps({'video_frame':i,'native_frame':1000+i,
               'time_s':i/20,'subject_id':42,'position_xyz_m':[x,-1.75,8 if 0<=x<=100 else 0],
               'velocity_xyz_mps':[speed,0,0],
               'provenance':'synthetic_native_sample'})+'\n')
    return history,context


def reject(history,context,expected):
    try:measure(history,context)
    except ValueError as exc:
        assert expected in str(exc)
        return str(exc)
    raise AssertionError('missing source accepted')


def main():
    above_h,above_c=fixture('above',13)
    below_h,below_c=fixture('below',9)
    above=measure(above_h,above_c);below=measure(below_h,below_c)
    assert above['on_structure_samples_above_posted_maximum']>0
    assert below['on_structure_samples_above_posted_maximum']==0
    lines=above_h.read_text().splitlines()
    missing=SCRATCH/'missing-frame.jsonl';missing.write_text('\n'.join(lines[:-1])+'\n')
    neg_frame=reject(missing,above_c,'missing original 600-frame')
    context=json.loads(above_c.read_text());context['native_sign_survey']=[]
    bad_sign=SCRATCH/'missing-sign.json';bad_sign.write_text(json.dumps(context)+'\n')
    neg_sign=reject(above_h,bad_sign,'Native bridge or sign survey missing')
    broken=[json.loads(line) for line in lines];del broken[160]['velocity_xyz_mps']
    bad_velocity=SCRATCH/'missing-velocity.jsonl'
    bad_velocity.write_text(''.join(json.dumps(row)+'\n' for row in broken))
    neg_velocity=reject(bad_velocity,above_c,'original velocity missing')
    print(json.dumps({'passed':True,'fixture_kind':'synthetic_native_sample',
      'above':{'on_structure_frames':above['on_structure_frames'],
        'maximum_on_structure_mph':above['maximum_on_structure_mph'],
        'samples_above_posting':above['on_structure_samples_above_posted_maximum']},
      'below':{'on_structure_frames':below['on_structure_frames'],
        'maximum_on_structure_mph':below['maximum_on_structure_mph'],
        'samples_above_posting':below['on_structure_samples_above_posted_maximum']},
      'negative_missing_frame':neg_frame,'negative_missing_sign':neg_sign,
      'negative_missing_velocity':neg_velocity,
      'measure_sha256':hashlib.sha256((HERE/'native/measure.py').read_bytes()).hexdigest()},sort_keys=True))
if __name__=='__main__':main()
