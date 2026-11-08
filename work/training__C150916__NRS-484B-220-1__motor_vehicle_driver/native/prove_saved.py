"""Retained synthetic saved one-way positives and altered-source negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from measure_saved import FILES, measure

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,rows):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def build_fixtures():
    folders={}
    for case in ('designated','opposite'):
        source=HERE/'drafts'/case/'primary'/'requested-tracks.jsonl'
        folder=HERE/'saved-fixtures'/case
        folder.mkdir(parents=True,exist_ok=True)
        rows=[];signs=[]
        for row in load(source):
            item=dict(row)
            item['case']=case
            item['native_frame']=1000+row['frame']
            item['ego_velocity_x_mps']=(1 if case=='designated' else -1)*row['ego_speed_mps']
            item['source_kind']='synthetic_cpu'
            rows.append(item)
            signs.append({'frame':row['frame'],'time_s':row['time_s'],
                          'native_frame':item['native_frame'],
                          'visible_sign_ids':[101] if case=='designated' and 10<=row['frame']<=100 else [],
                          'source_kind':'synthetic_cpu'})
        write(folder/'native-observed.jsonl',rows)
        write(folder/'sign-frames.jsonl',signs)
        (folder/'road-readback.json').write_text(json.dumps({
            'source_kind':'synthetic_cpu','driving_lane_ids':[-2,-1],
            'lane_direction_x':1,
            'sign_requests':{'101':{'type':'R6-1','direction_x':1},
                             '102':{'type':'R6-1','direction_x':1}}},indent=2)+'\n')
        (folder/'designation-record.json').write_text(json.dumps({
            'source_kind':'synthetic_cpu','designated_direction_x':1,
            'status':'synthetic_unverified','authority_document':None},indent=2)+'\n')
        folders[case]=folder
    return folders


def prove():
    folders=build_fixtures()
    positives=[]
    for case,folder in folders.items():
        result=measure(folder)
        if (result['direction_matches_designation']!=(case=='designated') or
                result['signed_ego_displacement_m']!=(95.6 if case=='designated' else -95.6) or
                result['delivery_ready'] or result['legal_verdict'] is not None):
            raise AssertionError('Synthetic one-way measurement differs')
        positives.append({'case':case,'source_hashes':result['source_hashes'],
                          'measurement':result})
    negatives=[]
    folder=folders['designated']
    for mutation in ('wrong_expected_hash','missing_saved_frame','wrong_velocity',
                     'missing_sign_frame','wrong_designation_direction'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            altered=Path(temporary)/'saved';shutil.copytree(folder,altered)
            if mutation=='missing_saved_frame':
                path=altered/'native-observed.jsonl';data=load(path);data.pop();write(path,data)
            elif mutation=='wrong_velocity':
                path=altered/'native-observed.jsonl';data=load(path)
                data[60]['ego_velocity_x_mps']=-8;write(path,data)
            elif mutation=='missing_sign_frame':
                path=altered/'sign-frames.jsonl';data=load(path);data.pop();write(path,data)
            elif mutation=='wrong_designation_direction':
                path=altered/'designation-record.json';item=json.loads(path.read_text())
                item['designated_direction_x']=-1;path.write_text(json.dumps(item)+'\n')
            try:
                measure(altered, {'native-observed.jsonl':'0'*64,
                                  **{name:sha(altered/name) for name in FILES if name!='native-observed.jsonl'}}
                        if mutation=='wrong_expected_hash' else None)
            except (ValueError,TypeError):negatives.append({'mutation':mutation,'rejected':True})
            else:raise AssertionError('Changed saved one-way source accepted')
    proof={'format':'c150916-saved-one-way-proof-v1','assignment_id':HERE.parent.name,
           'processor_sha256':sha(HERE/'measure_saved.py'),
           'positives':positives,'negative_controls':negatives,
           'original_native_observed':False,'legal_verdict':None,'delivery_ready':False}
    (HERE/'saved-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    proof=prove();print(json.dumps({'positives':len(proof['positives']),
                                    'negatives':len(proof['negative_controls'])}))
