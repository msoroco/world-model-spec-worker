"""Independently recompute four paired heavy-vehicle synthetic comparisons."""
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent
NATIVE = CASE/'native'
CANDIDATES = ('primary','fallback1','fallback2','fallback3')
MUTATIONS = ('longitudinal_center','speed','native_frame','body_x')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    proof_path = CASE/'controlled-comparison.json'
    proof = json.loads(proof_path.read_text())
    if (proof['format'] != 'c422978-heavy-controlled-synthetic-comparison-v1' or
            proof['saved_proof_sha256'] != sha(NATIVE/'saved-proof.json') or
            len(proof['pairs']) != 4 or len(proof['negatives']) != 16 or
            proof['original_native_observed'] or proof['accepted_comparison'] or
            proof['legal_verdict'] is not None or proof['delivery_ready']):
        raise ValueError('Controlled comparison proof scope differs')
    seen, total_rows = set(), 0
    for pair in proof['pairs']:
        candidate = pair['candidate']
        if candidate not in CANDIDATES or candidate in seen:
            raise ValueError('Controlled comparison candidate differs')
        seen.add(candidate)
        ref_path = NATIVE/'saved-fixtures/reference'/candidate/'native-observed.jsonl'
        con_path = NATIVE/'saved-fixtures/contrast'/candidate/'native-observed.jsonl'
        if pair['reference_sha256'] != sha(ref_path) or pair['contrast_sha256'] != sha(con_path):
            raise ValueError('Controlled saved-source hash differs')
        ref, con = lines(ref_path),lines(con_path)
        if len(ref)!=480 or len(con)!=480:
            raise ValueError('Controlled saved-source frame count differs')
        ref_hits, con_hits, con_inside = [], [], []
        for index,(a,b) in enumerate(zip(ref,con)):
            if (a['frame']!=index or b['frame']!=index or
                    a['native_frame']!=b['native_frame'] or
                    a['time_s']!=b['time_s'] or a['vehicle_blueprint']!=b['vehicle_blueprint'] or
                    a['speed_mps']!=b['speed_mps'] or
                    a['center_native_xy_m'][0]!=b['center_native_xy_m'][0] or
                    [p[0] for p in a['body_native_xy_m']] != [p[0] for p in b['body_native_xy_m']]):
                raise ValueError('Controlled paired field differs')
            ay=[p[1] for p in a['body_native_xy_m']]
            by=[p[1] for p in b['body_native_xy_m']]
            if a['speed_mps']>.1 and min(ay)<7.5 and max(ay)>3.5: ref_hits.append(index)
            if b['speed_mps']>.1 and min(by)<7.5 and max(by)>3.5: con_hits.append(index)
            if b['speed_mps']>.1 and min(by)>=3.5 and max(by)<=7.5: con_inside.append(index)
            total_rows += 2
        expected = {'reference_moving_overlap_frames':len(ref_hits),
                    'contrast_moving_overlap_frames':len(con_hits),
                    'contrast_first_overlap_frame':con_hits[0] if con_hits else None,
                    'contrast_full_body_inside_frames':len(con_inside),
                    'contrast_minus_reference_overlap_frames':len(con_hits)-len(ref_hits)}
        if pair['metric'] != expected or ref_hits or len(con_hits)<390:
            raise ValueError('Controlled comparison metric differs')
    if seen != set(CANDIDATES) or {(n['candidate'],n['mutation']) for n in proof['negatives']} != {
            (candidate,mutation) for candidate in CANDIDATES for mutation in MUTATIONS} or \
            not all(n['rejected'] is True for n in proof['negatives']):
        raise ValueError('Controlled comparison negative coverage differs')
    result={'format':'c422978-heavy-independent-comparison-audit-v1',
            'proof_sha256':sha(proof_path),'candidate_pairs':len(seen),
            'saved_rows_recomputed':total_rows,'recorded_negative_rejections':len(proof['negatives']),
            'accepted_comparison':False,'delivery_ready':False}
    (CASE/'controlled-comparison-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    result=audit()
    print(json.dumps({'pairs':result['candidate_pairs'],
                      'rows':result['saved_rows_recomputed'],
                      'negatives':result['recorded_negative_rejections']}))
