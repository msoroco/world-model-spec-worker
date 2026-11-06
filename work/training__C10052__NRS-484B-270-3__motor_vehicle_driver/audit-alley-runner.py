"""Four-candidate CPU preflight for the owned alley Native capture runner."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from alley_runner import check
from alley_engineering import parameters


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    config=json.loads((HERE/'native/alley-native-config.json').read_text())
    plan=json.loads((HERE/'alley-candidate-plan.json').read_text())
    assert plan['case_id']==config['case_id']
    assert config['case_suffix']=='probe_c_alley_entry'
    rows=[]
    for candidate in plan['candidates']:
        request=dict(config,candidate_id=candidate['id'])
        receipt=check(request)
        assert receipt['candidate']==candidate['id']
        assert receipt['camera_count']==4
        assert receipt['geometry']['physical_behavior_claimed'] is False
        assert receipt['native_imported'] is False and receipt['physical_success_claimed'] is False
        assert parameters(candidate['id'])==candidate['native_parameters']
        rows.append({'candidate':candidate['id'],
            'approach_start_x_m':candidate['native_parameters']['approach_start_x_m'],
            'turn_speed_mps':candidate['native_parameters']['turn_speed_mps'],
            'camera_profile':candidate['native_parameters']['camera_profile']})
    assert [r['candidate'] for r in rows]==['primary','fallback1','fallback2','fallback3']
    assert sha(HERE/'native/alley_runner.py')==plan['candidates'][0]['source_sha256']['alley_runner.py']
    assert sha(HERE/'native/alley-native-config.json')==plan['candidates'][0]['source_sha256']['alley-native-config.json']
    return {'passed':True,'preflight_candidates':4,'rows':rows,
        'native_execution_claimed':False,'runner_sha256':sha(HERE/'native/alley_runner.py')}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
