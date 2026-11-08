"""Independently recompute the synthetic original-schema control's phase evidence."""
import hashlib
import json
import math
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def audit():
    proof_path=CASE/'offline'/'proof-observed-schema.json';proof=json.loads(proof_path.read_text())
    if (proof['format']!='c131364-observed-schema-cpu-control-v1' or
        proof['original_native_observed'] or proof['delivery_ready'] or
        len(proof['positives'])!=2 or len(proof['negatives'])!=2 or
        any(not x['synthetic_original_schema_only'] for x in proof['positives']) or
        any(not x['rejected'] for x in proof['negatives'])):
        raise ValueError('Observed-schema control provenance differs')
    checked=0
    for witness in ('witness_1','witness_2'):
        bundle=CASE/'offline'/'bundles'/witness/'primary'
        original=rows(bundle/'connected-saved'/'native-observed.jsonl')
        requests=rows(bundle/'connected-requested-tracks.jsonl')
        phases=[x['road_id'] for x in original]
        if (len(original)!=240 or len(requests)!=240 or
            any(road not in (10,11,12) for road in phases) or
            phases!=sorted(phases)):
            raise ValueError('Observed-schema synthetic source route differs')
        exit_frames=phases.count(12)
        first_heading=requests[0]['ego_heading_deg']
        last_heading=requests[-1]['ego_heading_deg']
        change=math.degrees(math.atan2(math.sin(math.radians(last_heading-first_heading)),
            math.cos(math.radians(last_heading-first_heading))))
        item=next(x for x in proof['positives'] if x['witness']==witness)
        if item['observed_exit_frames']!=exit_frames or abs(item['heading_change_deg']-change)>1e-6:
            raise ValueError('Observed-schema control measurement differs')
        checked+=240
    result={'format':'c131364-independent-observed-schema-audit-v1',
        'proof_sha256':sha(proof_path),'synthetic_rows_recomputed':checked,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'audit-observed-schema.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
