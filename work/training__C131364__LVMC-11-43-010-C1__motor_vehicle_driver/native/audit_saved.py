"""Independently recompute synthetic lane occupancy and replay negatives."""
import hashlib
import json
import math
from pathlib import Path

from measure_saved import measure, rows, sha
from prove_saved import reject

HERE=Path(__file__).resolve().parent

def audit():
    proof_path=HERE/'saved-proof.json'
    proof=json.loads(proof_path.read_text())
    if (proof['format']!='c131364-saved-proof-v1' or
        len(proof['positives'])!=2 or len(proof['negative_controls'])!=6 or
        proof['original_native_observed'] or proof['actual_left_exit_observed'] or
        proof['delivery_ready']):
        raise ValueError('C131364 saved proof coverage differs')
    checked=0
    for item in proof['positives']:
        witness=item['witness'];folder=HERE/'saved-fixtures'/witness
        measured=measure(folder,item['measurement']['source_hashes'])
        if measured!=item['measurement']:
            raise ValueError('C131364 saved measurement differs')
        obs=rows(folder/'native-observed.jsonl')
        camera=rows(folder/'camera-frames.jsonl')
        expected_lane=-1 if witness=='witness_1' else -2
        inner,outer=(22,25.5) if expected_lane==-1 else (25.5,29)
        for i,(row,frame) in enumerate(zip(obs,camera)):
            if (row['frame']!=i or frame['frame']!=i or
                row['lane_id']!=expected_lane or
                frame['camera_frame']!=row['native_frame'] or
                not frame['left_lane_visible'] or
                not all(inner<=math.hypot(*point)<=outer for point in row['ego_body_xy_m']) or
                row['actual_exit_observed']):
                raise ValueError(f'C131364 independent saved row differs at {i}')
            checked+=1
    replayed=0
    for item in proof['negative_controls']:
        if not item['rejected'] or not reject(HERE/'saved-fixtures'/item['witness'],item['mutation']):
            raise ValueError('C131364 saved negative differs')
        replayed+=1
    result={'format':'c131364-independent-saved-audit-v1',
            'proof_sha256':sha(proof_path),'saved_rows_recomputed':checked,
            'negative_controls_replayed':replayed,
            'actual_left_exit_observed':False,'delivery_ready':False}
    (HERE/'saved-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
