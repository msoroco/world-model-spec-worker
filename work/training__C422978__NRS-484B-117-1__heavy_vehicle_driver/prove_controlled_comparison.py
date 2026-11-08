"""Compare exact paired synthetic heavy-vehicle saved rows; no legal verdict."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

CASE = Path(__file__).resolve().parent
NATIVE = CASE/'native'
CANDIDATES = ('primary','fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def fixed(row):
    return (row['frame'],row['native_frame'],row['time_s'],row['vehicle_blueprint'],
            row['speed_mps'],tuple(p[0] for p in row['body_native_xy_m']),
            row['center_native_xy_m'][0])


def compare(reference,contrast):
    ref, con = rows(reference), rows(contrast)
    if len(ref) != 480 or len(con) != 480:
        raise ValueError('Paired saved frame count differs')
    ref_overlap, con_overlap, con_inside = [], [], []
    for i,(a,b) in enumerate(zip(ref,con)):
        if fixed(a) != fixed(b) or a['source_kind'] != 'synthetic_cpu' or b['source_kind'] != 'synthetic_cpu':
            raise ValueError('Paired noncompared actor fields differ')
        if a['frame'] != i or b['frame'] != i:
            raise ValueError('Paired frame identity differs')
        ay = [p[1] for p in a['body_native_xy_m']]
        by = [p[1] for p in b['body_native_xy_m']]
        if a['speed_mps']>.1 and max(ay)>3.5 and min(ay)<7.5:
            ref_overlap.append(i)
        if b['speed_mps']>.1 and max(by)>3.5 and min(by)<7.5:
            con_overlap.append(i)
        if b['speed_mps']>.1 and min(by)>=3.5 and max(by)<=7.5:
            con_inside.append(i)
    if ref_overlap or len(con_overlap)<390 or len(con_inside)<370:
        raise ValueError('Paired synthetic sidewalk contrast absent')
    return {'reference_moving_overlap_frames':len(ref_overlap),
            'contrast_moving_overlap_frames':len(con_overlap),
            'contrast_first_overlap_frame':con_overlap[0],
            'contrast_full_body_inside_frames':len(con_inside),
            'contrast_minus_reference_overlap_frames':len(con_overlap)}


def rejected(fn):
    try:
        fn()
    except ValueError:
        return True
    raise AssertionError('Changed paired control accepted')


def prove():
    pairs, negatives = [], []
    for candidate in CANDIDATES:
        reference = NATIVE/'saved-fixtures/reference'/candidate/'native-observed.jsonl'
        contrast = NATIVE/'saved-fixtures/contrast'/candidate/'native-observed.jsonl'
        metric = compare(reference,contrast)
        pairs.append({'candidate':candidate,'reference_sha256':sha(reference),
                      'contrast_sha256':sha(contrast),'metric':metric})
        for mutation in ('longitudinal_center','speed','native_frame','body_x'):
            with tempfile.TemporaryDirectory(dir=CASE) as temporary:
                changed = Path(temporary)/'changed.jsonl'
                altered = rows(contrast)
                if mutation == 'longitudinal_center': altered[0]['center_native_xy_m'][0] += 1
                elif mutation == 'speed': altered[0]['speed_mps'] += 1
                elif mutation == 'native_frame': altered[0]['native_frame'] += 1
                else: altered[0]['body_native_xy_m'][0][0] += 1
                changed.write_text(''.join(json.dumps(row)+'\n' for row in altered))
                negatives.append({'candidate':candidate,'mutation':mutation,
                                  'rejected':rejected(lambda:compare(reference,changed))})
    proof = {'format':'c422978-heavy-controlled-synthetic-comparison-v1',
             'saved_proof_sha256':sha(NATIVE/'saved-proof.json'),
             'pairs':pairs,'negatives':negatives,
             'original_native_observed':False,'accepted_comparison':False,
             'legal_verdict':None,'delivery_ready':False}
    (CASE/'controlled-comparison.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'pairs':len(result['pairs']),'negatives':len(result['negatives'])}))
