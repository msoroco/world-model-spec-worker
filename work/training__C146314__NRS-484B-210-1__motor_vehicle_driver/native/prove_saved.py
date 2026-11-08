"""Exercise eight synthetic saved positives and two semantic negatives each."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from build_saved_fixture import build
from measure_saved import measure

CASE = Path(__file__).resolve().parents[1]
NATIVE = CASE/'native'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def put_rows(path, items):
    Path(path).write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in items))


def put(path, value):
    Path(path).write_text(json.dumps(value,indent=2)+'\n')


def reject(bundle, original, mutation):
    with tempfile.TemporaryDirectory(prefix='c146314-negative-') as tmp:
        saved = Path(tmp)/'saved'
        shutil.copytree(original,saved)
        if mutation == 'missing_camera_frame':
            path = saved/'camera-frames.jsonl'
            put_rows(path,rows(path)[:-1])
            key='camera_sha256'
        else:
            path=saved/'native-observed.jsonl'
            items=rows(path)
            items[80]['ego_body_xy_m'][0][1] += 2
            put_rows(path,items)
            key='observed_sha256'
        back=json.loads((saved/'readback.json').read_text())
        back[key]=sha(path)
        put(saved/'readback.json',back)
        try:
            measure(bundle,saved)
        except ValueError as exc:
            return str(exc)
        raise AssertionError('negative passed: '+mutation)


def prove():
    proofs=[]
    for witness in ('witness_1','witness_2'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle=NATIVE/'drafts'/witness/candidate
            saved=NATIVE/'saved-fixtures'/witness/candidate
            if saved.exists():
                shutil.rmtree(saved)
            build(bundle,saved)
            result=measure(bundle,saved)
            assert result['source_kind']=='synthetic_cpu'
            errors={kind:reject(bundle,saved,kind) for kind in
                    ('missing_camera_frame','changed_body_vertex')}
            proofs.append({'case_id':result['case_id'],
                           'candidate_id':candidate,
                           'saved_hashes':result['saved_hashes'],
                           'passing_right_geometry_frames':
                               result['passing_right_geometry_frames'],
                           'min_clearance_m':
                               result['min_ego_body_to_obstruction_clearance_m'],
                           'negative_errors':errors})
    receipt={'format':'c146314-saved-cpu-proof-v1',
             'positives':len(proofs),'semantic_negatives':2*len(proofs),
             'entries':proofs,'original_native_observed':False,
             'delivery_ready':False}
    put(NATIVE/'saved-proof.json',receipt)
    return receipt


if __name__=='__main__':
    x=prove()
    print(json.dumps({'positives':x['positives'],
                      'semantic_negatives':x['semantic_negatives'],
                      'geometry_frames':[e['passing_right_geometry_frames']
                                         for e in x['entries']],
                      'clearances':[e['min_clearance_m'] for e in x['entries']]}))
