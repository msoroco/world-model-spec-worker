"""Retained measured rotary fallback trigger positives and negatives."""
import json
import math
from pathlib import Path
import shutil
import tempfile

from measure_saved import FILES,sha
from triggers import route

HERE=Path(__file__).resolve().parent


def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,values):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in values))


def variants():
    source=HERE/'saved-fixtures'/'reference'
    parent=HERE/'trigger-fixtures'
    folders={}
    for name in ('entry-occluded','lane-deviation'):
        folder=parent/name
        if folder.exists():shutil.rmtree(folder)
        shutil.copytree(source,folder)
        if name=='entry-occluded':
            path=folder/'island-frames.jsonl';data=load(path)
            for row in data[:40]:row['island_visible']=False
            write(path,data)
        else:
            path=folder/'native-observed.jsonl';data=load(path)
            for row in data:
                x,y=row['ego_x_m'],row['ego_y_m']
                factor=(math.hypot(x,y)+.3)/math.hypot(x,y)
                dx,dy=x*(factor-1),y*(factor-1)
                row['ego_x_m']=round(x+dx,6)
                row['ego_y_m']=round(y+dy,6)
                row['ego_body_xy_m']=[[round(px+dx,6),round(py+dy,6)]
                                       for px,py in row['ego_body_xy_m']]
            write(path,data)
        folders[name]=folder
    return folders


def prove():
    folders={'reference':HERE/'saved-fixtures'/'reference',
             'contrast':HERE/'saved-fixtures'/'contrast',**variants()}
    positives=[]
    expected={'reference':(False,False,True),
              'contrast':(False,False,True),
              'entry-occluded':(True,False,True),
              'lane-deviation':(False,True,True)}
    for name,folder in folders.items():
        result=route(folder)
        flags=tuple(result['triggered'].values())
        if flags!=expected[name] or result['selected_candidate'] is not None:
            raise AssertionError('Rotary fallback routing differs: '+name)
        positives.append({'variant':name,'source_hashes':result['source_hashes'],
                          'routing':result})
    negatives=[]
    source=folders['reference']
    for mutation in ('wrong_expected_hash','missing_camera_frame','wrong_island_readback'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder=Path(temporary)/'saved';shutil.copytree(source,folder)
            if mutation=='missing_camera_frame':
                path=folder/'island-frames.jsonl';data=load(path);data.pop();write(path,data)
            elif mutation=='wrong_island_readback':
                path=folder/'island-readback.json';data=json.loads(path.read_text())
                data['center_xy_m']=[1,0];path.write_text(json.dumps(data)+'\n')
            hashes={name:sha(folder/name) for name in FILES}
            if mutation=='wrong_expected_hash':hashes['native-observed.jsonl']='0'*64
            try:route(folder,hashes if mutation=='wrong_expected_hash' else None)
            except (ValueError,TypeError):negatives.append({'mutation':mutation,'rejected':True})
            else:raise AssertionError('Changed rotary trigger source accepted')
    proof={'format':'c234827-measured-trigger-proof-v1',
        'assignment_id':HERE.parent.name,
        'processor_sha256':sha(HERE/'triggers.py'),
        'saved_processor_sha256':sha(HERE/'measure_saved.py'),
        'positives':positives,'negative_controls':negatives,
        'original_native_observed':False,'selected_candidate':None,
        'delivery_ready':False}
    (HERE/'trigger-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
                                     'negatives':len(result['negative_controls'])}))
