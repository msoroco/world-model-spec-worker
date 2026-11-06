"""Source-hashed 480-frame corner contrast and adversarial CPU fixtures."""
from __future__ import annotations
import hashlib,json,tempfile,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from geometry import body,check,pose,TOTAL_REVERSE_DISTANCE
from measure import measure

JUNCTION=[[-7,-7],[7,-7],[7,7],[-7,7]]
CROSSWALK=[[-19,-3.5],[-15,-3.5],[-15,3.5],[-19,3.5]]

def rows(suffix):
    out=[]
    for i in range(480):
        progress=min(i/200,1)
        x,y,heading=pose(suffix,progress)
        out.append({'video_frame':i,'native_frame':3000+i,'time_s':i/20,
                    'native_center_xy_m':[x,y],'heading_deg':heading,
                    'body_xy_m':body(x,y,heading),
                    'signed_forward_velocity_m_s':-TOTAL_REVERSE_DISTANCE/10 if i<=200 else 0,
                    'native_corner_survey':True,
                    'intersection_polygon_xy_m':JUNCTION,
                    'crosswalk_polygon_xy_m':CROSSWALK})
    return out

def save(path,items):
    path.write_text(''.join(json.dumps(item,separators=(',',':'))+'\n' for item in items))
    return hashlib.sha256(path.read_bytes()).hexdigest()

def reject(path,items,expected):
    digest=save(path,items)
    try:measure(path,digest)
    except ValueError as e:
        if expected not in str(e):raise AssertionError(str(e)) from e
    else:raise AssertionError('Corrupt corner source accepted')

def main():
    geometry=check();out={}
    for suffix in ('condition_a','condition_b'):
        folder=HERE/'fixtures'/suffix;folder.mkdir(parents=True,exist_ok=True)
        source=folder/'native_samples.jsonl';values=rows(suffix)
        digest=save(source,values);result=measure(source,digest)
        expected='backing_straight_through_intersection' if suffix=='condition_a' else 'backing_around_street_corner'
        if result['relation']!=expected:raise AssertionError('Corner relation differs')
        with tempfile.TemporaryDirectory(prefix='c110812-neg-') as tmp:
            temp=Path(tmp)
            bad=[r.copy() for r in values];bad[100]=bad[100]|{'native_frame':9999}
            reject(temp/'frame.jsonl',bad,'Original frame join')
            bad=[r.copy() for r in values];bad[100]=bad[100]|{'signed_forward_velocity_m_s':.2}
            reject(temp/'sign.jsonl',bad,'Nonbacking velocity disagrees')
            bad=[r.copy() for r in values];bad[100]=bad[100]|{'native_corner_survey':False}
            reject(temp/'survey.jsonl',bad,'corner map survey absent')
            bad=[r.copy() for r in values];bad[100]=bad[100]|{'crosswalk_polygon_xy_m':[[0,0],[1,0],[1,1],[0,1]]}
            reject(temp/'crosswalk.jsonl',bad,'corner map survey absent')
            source.write_bytes(source.read_bytes()+b' ')
            try:measure(source,digest)
            except ValueError as e:
                if 'hash differs' not in str(e):raise
            else:raise AssertionError('Source mutation accepted')
            source.write_bytes(source.read_bytes()[:-1])
        out[suffix]={'relation':result['relation'],'corner_event_frames':result['corner_event_frames'],
                     'heading_change_deg':result['max_reverse_heading_change_deg'],
                     'source_sha256':digest,'adversarial_negatives':5}
    print(json.dumps({'passed':True,'scope':'authored and synthetic CPU only','geometry':geometry,
                      'cases':out},indent=2))
if __name__=='__main__':main()
