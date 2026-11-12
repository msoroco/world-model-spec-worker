"""Check selected diagnostic source chains while refusing delivery acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

from physical_motion_audit import audit as motion_audit, rows
from delivery_audit import joined_observer_distances

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CAMERAS=('overview','approach','reference_corner','driver_reference')
NAMES=('native_body_history.jsonl','trace.jsonl','capture/evidence.jsonl',
       'video_frames.jsonl','driver_eye_rays.jsonl','road.xodr',
       *(camera+'.mkv' for camera in CAMERAS))

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)

def audit(case,negative=False):
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    entry=next((e for e in manifest['cases'] if e['case_id']==case),None)
    require(entry is not None,'Unselected C104538 case')
    expected='0'*64 if negative else entry['construction_sha256']
    require(sha(HERE/entry['construction'])==expected,
            'Delivery construction differs from selected manifest')
    suffix=case.removeprefix(HERE.name+'__')
    prefix='below' if suffix=='below_500_ft' else suffix
    attempt=ROOT/'.runtime-work'/f'c104538-update023-{prefix}-primary-compat'
    saved=json.loads((ROOT/'.runtime-work'/f'c104538-update023-{prefix}-primary-saved/v0001/processing.json').read_text())
    compat=json.loads((HERE/entry['compatibility']['receipt']).read_text())
    physical=json.loads((HERE/entry['physical_preparation']['receipt']).read_text())
    require(compat['passed'] is True and compat['case_id']==case and
            compat['construction_sha256']==entry['construction_sha256'],
            'Selected compatibility differs')
    require(saved['passed'] is True and saved['recorded_only'] is True and
            saved['case_id']==case and saved['candidate_id']=='primary' and
            saved['native_revision']['construction_sha256']==entry['construction_sha256'] and
            saved['originals_preserved'] is True and saved['missing_evidence'] is False and
            saved['physical_acceptance_claimed'] is False and saved['legal_acceptance_claimed'] is False and
            saved['timestamp_joins']['passed'] is True and saved['timestamp_joins']['frames']==480,
            'Selected saved diagnostic processing differs')
    require(physical['fixtures_are_cpu_mocks'] is True and
            physical['original_native_motion_verified'] is False and
            physical['original_two_direction_pixels_verified'] is False,
            'Physical mock promoted to original')
    hashes={}
    for name in NAMES:
        source=attempt/name
        require(source.is_file(),'Missing diagnostic source: '+name)
        digest=sha(source)
        require(saved['original_source_hashes'].get(name)==digest,
                'Saved diagnostic source changed: '+name)
        hashes[name]=digest
    mapping,trace,evidence,rays=(rows(attempt/name) for name in
        ('video_frames.jsonl','trace.jsonl','capture/evidence.jsonl','driver_eye_rays.jsonl'))
    distances=joined_observer_distances(mapping,trace,evidence,rays)
    require(all(len(v)==480 for v in distances.values()),
            'Both approach direction histories incomplete')
    require(all(movement.get('speed_provenance')=='synthetic_native_sample' and
                capture['ego'].get('speed_provenance')=='synthetic_native_sample'
                for movement,capture in zip(trace,evidence)),
            'Synthetic speed provenance differs')
    motion=motion_audit(attempt,case,diagnostic=True)
    require(motion['source_shaped_motion_status']=='met' and
            motion['native_motion_status']=='unverified',
            'Diagnostic reversal or original Native status differs')
    try:motion_audit(attempt,case)
    except ValueError as exc:
        require('Synthetic source cannot prove original Native motion' in str(exc),
                'Unexpected production audit rejection')
    else:raise AssertionError('Synthetic motion accepted as original')
    result=json.loads((attempt/'result.json').read_text())
    require(saved['result_sha256']==sha(attempt/'result.json') and
            result['provenance_kind']=='synthetic_local_diagnostic' and
            result['maneuver_completed'] is False and result['accepted'] is False and
            result['legal_verdict_claimed'] is False,
            'Diagnostic result claimed acceptance')
    return {'case_id':case,'construction_sha256':entry['construction_sha256'],
            'source_shape_passed':True,'source_sha256':hashes,
            'joined_frames':480,'joined_directions':sorted(distances),
            'four_camera_sources':list(CAMERAS),'original_pixels_reviewed':False,
            'delivery_accepted':False,'original_native_motion_verified':False,
            'auditor_sha256':sha(Path(__file__))}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--negative',action='store_true')
    a=p.parse_args();print(json.dumps(audit(a.case,a.negative)))
