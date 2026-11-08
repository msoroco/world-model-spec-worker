"""Retain measured LVMC fallback variants and altered-source controls."""
import copy
import json
import math
from pathlib import Path
import shutil
import tempfile

from measure_saved import FILES,sha
from triggers import route

HERE=Path(__file__).resolve().parent
OUT=HERE/'trigger-fixtures'


def write_rows(path,rows):
    path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def make_variants():
    if OUT.exists():shutil.rmtree(OUT)
    source=HERE/'saved-fixtures'/'witness_1'
    for name in ('entry-occluded','lane-deviation'):
        folder=OUT/name;shutil.copytree(source,folder)
        if name=='entry-occluded':
            path=folder/'roundabout-frames.jsonl'
            frames=[json.loads(s) for s in path.read_text().splitlines()]
            for row in frames[:40]:row['roundabout_visible']=False
            write_rows(path,frames)
        else:
            path=folder/'native-observed.jsonl'
            rows=[json.loads(s) for s in path.read_text().splitlines()]
            for row in rows:
                x,y=row['ego_x_m'],row['ego_y_m']
                length=math.hypot(x,y);dx=.3*x/length;dy=.3*y/length
                row['ego_x_m']=round(x+dx,6);row['ego_y_m']=round(y+dy,6)
                row['ego_body_xy_m']=[[round(px+dx,6),round(py+dy,6)]
                    for px,py in row['ego_body_xy_m']]
            write_rows(path,rows)


def reject(mutation):
    source=HERE/'saved-fixtures'/'witness_1'
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary)/'saved';shutil.copytree(source,folder)
        expected={name:sha(folder/name) for name in FILES}
        if mutation=='changed_observation':
            path=folder/'roundabout-frames.jsonl'
            rows=[json.loads(s) for s in path.read_text().splitlines()]
            rows[0]['roundabout_visible']=False;write_rows(path,rows)
        elif mutation=='changed_motion':
            path=folder/'native-observed.jsonl'
            rows=[json.loads(s) for s in path.read_text().splitlines()]
            rows[60]['ego_speed_mps']+=3;write_rows(path,rows)
        elif mutation=='changed_readback':
            path=folder/'roundabout-readback.json'
            value=json.loads(path.read_text());value['center_xy_m']=[1,0]
            path.write_text(json.dumps(value,indent=2)+'\n')
        else:raise ValueError('Unknown LVMC trigger mutation')
        try:route(folder,expected)
        except ValueError:return {'mutation':mutation,'rejected':True}
        raise AssertionError('LVMC trigger accepted '+mutation)


def prove():
    make_variants()
    source=HERE/'saved-fixtures'
    variants={'witness_1':source/'witness_1',
              'witness_2':source/'witness_2',
              'entry-occluded':OUT/'entry-occluded',
              'lane-deviation':OUT/'lane-deviation'}
    positives=[]
    for name,folder in variants.items():
        result=route(folder)
        positives.append({'variant':name,'source_hashes':result['source_hashes'],
            'routing':result})
    expected={'witness_1':(False,False,True),
              'witness_2':(False,False,True),
              'entry-occluded':(True,False,True),
              'lane-deviation':(False,True,True)}
    for row in positives:
        flags=row['routing']['triggered']
        actual=(flags['fallback1_slow_for_entry_visibility'],
                flags['fallback2_outer_lane_for_deviation'],
                flags['fallback3_stop_for_unverified_roundabout_or_control'])
        if actual!=expected[row['variant']] or row['routing']['selected_candidate'] is not None:
            raise AssertionError('LVMC measured fallback variant differs')
    negatives=[reject(name) for name in
        ('changed_observation','changed_motion','changed_readback')]
    proof={'format':'c234827-lvmc-trigger-proof-v1',
        'processor_sha256':sha(HERE/'triggers.py'),
        'saved_processor_sha256':sha(HERE/'measure_saved.py'),
        'positives':positives,'negative_controls':negatives,
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'trigger-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
        'negatives':len(result['negative_controls'])}))
