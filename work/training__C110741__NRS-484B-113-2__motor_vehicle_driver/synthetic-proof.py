"""Persist and adversarially test the 480-frame C110741 reverse pair."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from geometry import STOPS, body, check
from measure import measure


def rows(suffix):
    stop=STOPS[suffix]
    out=[]
    for i in range(480):
        fraction=min(i/199,1)
        x=round(-10+(stop+10)*fraction,5)
        out.append({'video_frame':i,'native_frame':2000+i,'time_s':i/20,
                    'native_center_xy_m':[x,-1.75],
                    'body_xy_m':body(x),
                    'signed_forward_velocity_m_s':(stop+10)/(199*.05) if i<200 else 0,
                    'native_crosswalk_survey':True,
                    'crosswalk_polygon_xy_m':[[-19,-3.5],[-15,-3.5],[-15,3.5],[-19,3.5]],
                    'heading_deg':0})
    return out


def save(path,items):
    path.write_text(''.join(json.dumps(item,separators=(',',':'))+'\n' for item in items))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject(path,items,message):
    digest=save(path,items)
    try:measure(path,digest)
    except ValueError as exc:
        if message not in str(exc):raise AssertionError(str(exc)) from exc
    else:raise AssertionError('Corrupt reverse source accepted')


def main():
    geometry=check();out={}
    for suffix in ('condition_a','condition_b'):
        folder=HERE/'fixtures'/suffix;folder.mkdir(parents=True,exist_ok=True)
        source=folder/'native_samples.jsonl';values=rows(suffix);digest=save(source,values)
        result=measure(source,digest)
        expected='backing_clear_of_crosswalk' if suffix=='condition_a' else 'backing_over_crosswalk'
        if result['relation']!=expected:raise AssertionError('Positive reverse relation differs')
        with tempfile.TemporaryDirectory(prefix='c110741-neg-') as scratch:
            temp=Path(scratch)
            bad=[r.copy() for r in values];bad[100]=bad[100]|{'native_frame':9999}
            reject(temp/'gap.jsonl',bad,'Original frame join')
            bad=[r.copy() for r in values];bad[100]=bad[100]|{'signed_forward_velocity_m_s':.2}
            reject(temp/'sign.jsonl',bad,'Nonbacking velocity disagrees')
            bad=[r.copy() for r in values];bad[100]=bad[100]|{'native_crosswalk_survey':False}
            reject(temp/'survey.jsonl',bad,'crosswalk map survey absent')
            source.write_bytes(source.read_bytes()+b' ')
            try:measure(source,digest)
            except ValueError as exc:
                if 'hash differs' not in str(exc):raise
            else:raise AssertionError('Source mutation accepted')
            source.write_bytes(source.read_bytes()[:-1])
        out[suffix]={'relation':result['relation'],'event_frames':result['backing_crosswalk_event_frames'],
                     'max_overlap_m2':result['max_backing_crosswalk_overlap_m2'],
                     'source_sha256':digest,'adversarial_negatives':4}
    print(json.dumps({'passed':True,'scope':'authored and synthetic CPU only',
                      'geometry':geometry,'cases':out},indent=2))


if __name__=='__main__':main()
