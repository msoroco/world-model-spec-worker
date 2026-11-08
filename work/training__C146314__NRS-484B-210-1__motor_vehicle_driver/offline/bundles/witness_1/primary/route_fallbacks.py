"""Route measured C146314 diagnostics; preserve original-source distinction."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import measure

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def route(bundle,saved):
    bundle,saved=Path(bundle),Path(saved)
    metric=measure(bundle,saved)
    contract=json.loads((HERE/'measurement-contract.json').read_text())
    back=json.loads((saved/'readback.json').read_text())
    clearance=metric['min_ego_body_to_obstruction_clearance_m']
    triggers={
        'fallback1': {'metric':'min_ego_body_to_obstruction_clearance_m',
            'value':clearance,'threshold_m':0.5,
            'triggered':clearance is not None and clearance<0.5},
        'fallback2': {'metric':'original_pixel_review_complete',
            'value':back['object_pixel_reviewed'],
            'triggered':not back['object_pixel_reviewed']},
        'fallback3': {'metric':'original_one_way_and_pavement_verified',
            'value':back['one_way_designation_verified'] and
                    back['pavement_condition_verified'],
            'triggered':not (back['one_way_designation_verified'] and
                             back['pavement_condition_verified'])},
    }
    return {'format':'c146314-measured-fallback-router-v1',
        'case_id':metric['case_id'],'candidate_id':metric['candidate_id'],
        'source_kind':metric['source_kind'],
        'measurement_contract_sha256':sha(HERE/'measurement-contract.json'),
        'saved_hashes':metric['saved_hashes'],'triggers':triggers,
        'physical_clearance_verified':False,
        'selected_fallback':None,'delivery_ready':False}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(route(a.bundle,a.saved_dir),indent=2))
