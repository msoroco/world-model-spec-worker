"""Exercise C146314 raw-to-saved joins and independent rejection controls."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

CASE=Path(__file__).resolve().parent
sys.path.insert(0,str(CASE/'native'))
import fixture_raw
import prepare_raw
import measure_prepared

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_rows(path,items):
    path.write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in items))
def rows(path): return [json.loads(x) for x in path.read_text().splitlines()]

def audit_join(raw,saved):
    source=rows(raw/'native-raw-actors.jsonl')
    target=rows(saved/'native-observed.jsonl')
    camera=rows(saved/'camera-frames.jsonl')
    review=rows(saved/'frame-review.jsonl')
    assert len(source)==len(target)==len(camera)==len(review)==240
    for i,(a,b,c,r) in enumerate(zip(source,target,camera,review)):
        assert a['frame']==b['frame']==c['frame']==r['frame']==i
        assert a['native_frame']==b['native_frame']==c['native_frame']==r['native_frame']
        for role in ('ego','lead','obstruction'):
            assert b[role]==a[role]
        assert c['video_frame']==i and r['review_provenance']=='synthetic_cpu'

def prove():
    checks=[];negative=[]
    for bundle in sorted((CASE/'offline/bundles').glob('*/*')):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);raw=root/'raw';saved=root/'saved'
            fixture_raw.build(bundle,raw)
            receipt=prepare_raw.prepare(bundle,raw,saved,synthetic_cpu=True)
            audit_join(raw,saved)
            measured=measure_prepared.measure(bundle,saved)
            assert measured['frames']==240 and not measured['delivery_ready']
            assert receipt['saved_hashes']['native-observed.jsonl']==sha(
                saved/'native-observed.jsonl')
            checks.append(str(bundle.relative_to(CASE)))
            for kind in ('changed_video_join','changed_body_vertex','missing_original_media'):
                with tempfile.TemporaryDirectory() as folder2:
                    other=Path(folder2);altered=other/'raw'
                    fixture_raw.build(bundle,altered)
                    if kind=='changed_video_join':
                        p=altered/'video_frames.jsonl';items=rows(p)
                        items[100]['native_frame']+=1;write_rows(p,items)
                    elif kind=='changed_body_vertex':
                        p=altered/'native-raw-actors.jsonl';items=rows(p)
                        items[100]['ego']['body_native_xyz_m'][0][0]+=2
                        write_rows(p,items)
                    else:
                        p=altered/'native-map-readback.json';value=json.loads(p.read_text())
                        value['source_kind']='original_native'
                        p.write_text(json.dumps(value)+'\n')
                        p=altered/'native-raw-actors.jsonl';items=rows(p)
                        for item in items:item['source_kind']='original_native'
                        write_rows(p,items)
                        p=altered/'frame-review.jsonl';items=rows(p)
                        for item in items:
                            item['source_kind']='original_native'
                            item['review_provenance']='human_frame_review'
                        write_rows(p,items)
                    try:
                        prepare_raw.prepare(bundle,altered,other/'saved',
                            synthetic_cpu=kind!='missing_original_media')
                    except (ValueError,FileNotFoundError,RuntimeError):
                        negative.append({'bundle':str(bundle.relative_to(CASE)),
                                         'mutation':kind})
                    else:
                        raise AssertionError('raw mutation accepted: '+kind)
    receipt={'format':'c146314-raw-preparation-cpu-proof-v1',
        'positive_bundles':checks,'independent_join_rows':1920,
        'prepared_measurements':8,
        'negative_controls':negative,'original_native_observed':False,
        'strict_v2_compatibility':False,'delivery_ready':False}
    (CASE/'offline/raw-preparation-proof.json').write_text(
        json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    result=prove()
    print(json.dumps({'positives':len(result['positive_bundles']),
                      'negatives':len(result['negative_controls']),
                      'independent_join_rows':result['independent_join_rows']}))
