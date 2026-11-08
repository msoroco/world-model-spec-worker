"""Retained measured one-way routing positives and altered-source negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from triggers import route

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,data):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in data))


def build_variant(name,mutation):
    source=HERE/'saved-fixtures'/'designated'
    target=HERE/'trigger-fixtures'/name
    if target.exists():shutil.rmtree(target)
    shutil.copytree(source,target)
    if mutation=='entry_occluded':
        path=target/'sign-frames.jsonl';rows=load(path)
        for row in rows[:40]:row['visible_sign_ids']=[]
        write(path,rows)
    elif mutation=='lane_deviation':
        path=target/'native-observed.jsonl';rows=load(path)
        rows[60]['ego_y_m']=-1.45
        write(path,rows)
    return target


def prove():
    folders={'designated':HERE/'saved-fixtures'/'designated',
             'opposite':HERE/'saved-fixtures'/'opposite',
             'entry_occluded':build_variant('entry-occluded','entry_occluded'),
             'lane_deviation':build_variant('lane-deviation','lane_deviation')}
    expected={'designated':(False,False,True),'opposite':(True,False,True),
              'entry_occluded':(True,False,True),'lane_deviation':(False,True,True)}
    positives=[]
    for name,folder in folders.items():
        result=route(folder)
        flags=tuple(result['triggered'].values())
        if flags!=expected[name] or result['selected_candidate'] is not None or result['delivery_ready']:
            raise AssertionError('Measured one-way fallback routing differs')
        positives.append({'variant':name,'source_hashes':result['source_hashes'],
                          'triggered':result['triggered']})
    negatives=[]
    for mutation in ('wrong_expected_hash','unknown_sign_id','bad_lane_offset'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            altered=Path(temporary)/'saved';shutil.copytree(folders['designated'],altered)
            if mutation=='unknown_sign_id':
                path=altered/'sign-frames.jsonl';rows=load(path)
                rows[60]['visible_sign_ids']=[999];write(path,rows)
            elif mutation=='bad_lane_offset':
                path=altered/'native-observed.jsonl';rows=load(path)
                rows[60]['ego_y_m']=-.75;write(path,rows)
            try:
                route(altered,{'native-observed.jsonl':'0'*64} if mutation=='wrong_expected_hash' else None)
            except (ValueError,TypeError):negatives.append({'mutation':mutation,'rejected':True})
            else:raise AssertionError('Changed measured routing source accepted')
    proof={'format':'c150916-measured-trigger-proof-v1','assignment_id':HERE.parent.name,
           'trigger_processor_sha256':sha(HERE/'triggers.py'),
           'saved_processor_sha256':sha(HERE/'measure_saved.py'),
           'positives':positives,'negative_controls':negatives,
           'original_native_observed':False,'selected_candidate':None,
           'delivery_ready':False}
    (HERE/'trigger-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    proof=prove();print(json.dumps({'positives':len(proof['positives']),
                                    'negatives':len(proof['negative_controls'])}))
