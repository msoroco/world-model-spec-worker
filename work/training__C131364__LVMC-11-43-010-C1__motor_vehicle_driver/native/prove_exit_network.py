"""Replay connected-exit construction with changed-map and changed-track controls."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import audit_exit_network as checker

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def prove():
    positive=checker.audit()
    negatives=[]
    for mutation in ('changed_map','changed_track'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            copied=Path(temporary)/'native';copied.mkdir()
            shutil.copy2(HERE/'left-exit-road.xodr',copied/'left-exit-road.xodr')
            shutil.copytree(HERE/'exit-network-drafts',copied/'exit-network-drafts')
            if mutation=='changed_map':
                path=copied/'left-exit-road.xodr'
            else:
                path=copied/'exit-network-drafts'/'witness_1'/'primary'/'requested-tracks.jsonl'
            path.write_bytes(path.read_bytes()+b' ')
            original=checker.HERE
            try:
                checker.HERE=copied
                try:checker.audit()
                except ValueError:pass
                else:raise ValueError(f'C131364 {mutation} accepted')
            finally:checker.HERE=original
            negatives.append({'mutation':mutation,'rejected':True})
    result={'format':'c131364-connected-exit-proof-v1',
            'construction_manifest_sha256':sha(HERE/'exit-network-drafts'/'manifest.json'),
            'independent_audit_sha256':sha(HERE/'exit-network-audit.json'),
            'positive':{'roads_checked':positive['roads_checked'],
                        'requested_rows_checked':positive['requested_rows_checked'],
                        'complete_authored_exit_paths':positive['complete_authored_exit_paths']},
            'negative_controls':negatives,'original_native_observed':False,
            'physical_roundabout_verified':False,'delivery_ready':False}
    (HERE/'exit-network-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(prove()))
