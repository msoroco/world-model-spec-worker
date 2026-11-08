"""Independently recompute controlled fields and reject changed pair sources."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from compare_saved import compare
from measure_saved import rows

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    path=HERE/'saved-comparison.json'
    saved=json.loads(path.read_text())
    actual=compare()
    if saved!=actual:raise ValueError('Saved comparison differs from source')
    a=rows(HERE/'saved-fixtures'/'witness_1'/'native-observed.jsonl')
    b=rows(HERE/'saved-fixtures'/'witness_2'/'native-observed.jsonl')
    if len(a)!=240 or len(b)!=240:raise ValueError('Controlled row coverage differs')
    for i,(x,y) in enumerate(zip(a,b)):
        if (x['frame']!=y['frame'] or x['time_s']!=y['time_s'] or
            x['lane_id']!=y['lane_id'] or x['ego_speed_mps']!=y['ego_speed_mps'] or
            abs(x['ego_x_m']-y['ego_x_m'])>1e-6 or
            abs(x['ego_y_m']+y['ego_y_m'])>1e-6):
            raise ValueError(f'Independent controlled pair differs at {i}')
    with tempfile.TemporaryDirectory(dir=HERE) as temporary:
        changed=Path(temporary)/'witness_2'
        shutil.copytree(HERE/'saved-fixtures'/'witness_2',changed)
        entries=rows(changed/'native-observed.jsonl')
        entries[50]['ego_speed_mps']+=.5
        (changed/'native-observed.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in entries))
        try:compare(second=changed)
        except ValueError:pass
        else:raise ValueError('Changed speed accepted')
    result={'format':'c234827-lvmc-independent-comparison-audit-v1',
            'comparison_sha256':sha(path),'rows_recomputed':480,
            'negative_controls_replayed':1,'delivery_ready':False}
    (HERE/'saved-comparison-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
