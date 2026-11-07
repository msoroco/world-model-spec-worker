"""Independent structural audit of all eight unselected 3(a) CPU policies."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    value=json.loads((FOLDER/'draft-construction/candidate-manifest.json').read_text())
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    assert value['assignment_id']==plan['assignment_id']
    assert value['law_text_sha256']==plan['source_law']['text_sha256']
    assert value['map_sha256']==sha(FOLDER/'draft-construction/scene.xodr')
    assert value['status']=='unselected_prebundle'
    assert value['exact_pinned_offline_passed'] is False
    assert value['portable_compatibility_passed'] is False
    for name,digest in value['source_sha256'].items():
        assert digest==sha(FOLDER/'native'/name)
    rows=value['cases']
    assert len(rows)==8
    for case in ('controlled_1','controlled_2'):
        group=[r for r in rows if r['case_id']==plan['assignment_id']+'__'+case]
        assert {r['candidate_id'] for r in group}=={'primary','fallback1','fallback2','fallback3'}
        assert len({r['purpose_request'] for r in group})==1
        assert all(r['purpose_request_is_observation'] is False and
                   r['physical_success_claimed'] is False for r in group)
        assert len({(r['authored_route_sha256'],r['controller_knobs']['lookahead_base_m'],
                    r['camera_plan'][1]['fov_deg']) for r in group})==4
        primary=next(r for r in group if r['candidate_id']=='primary')
        fallback1=next(r for r in group if r['candidate_id']=='fallback1')
        fallback2=next(r for r in group if r['candidate_id']=='fallback2')
        fallback3=next(r for r in group if r['candidate_id']=='fallback3')
        assert fallback1['entry_advance_m']>primary['entry_advance_m']
        assert fallback2['controller_knobs']['lookahead_base_m']<primary['controller_knobs']['lookahead_base_m']
        assert fallback3['camera_plan'][1]['fov_deg']>primary['camera_plan'][1]['fov_deg']
        assert all(r['trigger'] is not None for r in group if r['candidate_id']!='primary')
    return {'passed':True,'cases':2,'candidate_rows':8,'physical_or_delivery_claimed':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
