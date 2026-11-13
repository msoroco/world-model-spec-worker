"""Check safety-only turn sources with fixed no-signal controls."""
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
NEAR = ROOT.name + '__pedestrian_no_horn_before_turn'
DISTANT = ROOT.name + '__safety_only_distant_users'


def require(value, message):
    if not value:
        raise ValueError(message)


def audit(receipts=None):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entries = {x['case_id']: x for x in manifest['cases']}
    require(NEAR in entries and DISTANT in entries, 'Missing safety-only exact case')
    values = {}
    for case in (NEAR, DISTANT):
        entry = entries[case]
        receipt_path = ROOT / entry['compatibility']['receipt']
        require(sha256(receipt_path.read_bytes()).hexdigest() == entry['compatibility']['sha256'],
                'Stale safety-only receipt')
        receipt = (receipts or {}).get(case) or json.loads(receipt_path.read_text())
        require(receipt['passed'] and receipt['case_id'] == case
                and receipt['construction_sha256'] == entry['construction_sha256'],
                'Wrong safety-only receipt or construction')
        source = ROOT / entry['construction']
        require(sha256(source.read_bytes()).hexdigest() == entry['construction_sha256'],
                'Stale safety-only construction')
        construction = json.loads(source.read_text())
        config = json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json'))
        require(config['selected_case_id'] == case, 'Wrong safety-only identity')
        runner = next(x['content'] for x in construction['files'] if x['path']=='runner.py')
        value = receipt['measurement_examples']['turn_signal_observation']['value']
        require(value['format']=='worker-turn-signal-observation', 'Wrong safety-only measurement')
        values[case] = config, runner, value
    near_config, near_runner, near = values[NEAR]
    far_config, far_runner, far = values[DISTANT]
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','cameras','required_atoms','source_packets'):
        require(near_config[key] == far_config[key], 'Safety-only fixed condition changed: '+key)
    require(near_config['engineering']==far_config['engineering'], 'Turn controller changed')
    require('carla.Location(x=6, y=2, z=.5)' in near_runner
            and 'participant_spawn_transform' in far_runner
            and 'left_m=14.0' in far_runner, 'Pedestrian geometry contrast absent')
    for key in ('ego_turn_motion.jsonl','ego_signal_audio.jsonl'):
        require(near['sources'][key]==far['sources'][key], 'Fixed safety-only source changed: '+key)
    require(near['sources']['participant_bodies.jsonl']!=far['sources']['participant_bodies.jsonl']
            and near['sources']['affected_participants.json']!=far['sources']['affected_participants.json'],
            'Pedestrian geometry/context did not change')
    require(near['turn_onset_frame']==far['turn_onset_frame']
            and near['turn_direction']==far['turn_direction'], 'Turn motion contrast changed')
    require(near['pedestrian_may_be_affected'] and not far['pedestrian_may_be_affected']
            and not near['vehicle_may_be_affected'] and not far['vehicle_may_be_affected'],
            'Potential-effect construction context differs')
    require(near['max_pre_turn_listener_audio_rms']==far['max_pre_turn_listener_audio_rms']==0.0
            and not near['pre_turn_indicator_frames'] and not far['pre_turn_indicator_frames'],
            'Safety-only comparison changed the signal')
    near_gap=near['participant_clearance']['ped_listener']['minimum_sampled_surface_gap_m']
    far_gap=far['participant_clearance']['ped_listener']['minimum_sampled_surface_gap_m']
    require(far_gap>near_gap, 'Measured safety-only clearance did not increase')
    return {'format':'worker-safety-only-comparison-audit','passed':True,
            'comparison_id':'safety_only_condition','case_ids':[NEAR,DISTANT],
            'minimum_sampled_pedestrian_gap_m':[near_gap,far_gap],
            'scope':'source-shaped CPU comparison; potential effect and reasonable safety unjudged'}


if __name__=='__main__':
    result=audit()
    if '--selftest' in sys.argv:
        manifest=json.loads((ROOT/'execution-manifest.json').read_text())
        entry=next(x for x in manifest['cases'] if x['case_id']==DISTANT)
        forged=json.loads((ROOT/entry['compatibility']['receipt']).read_text())
        forged['measurement_examples']['turn_signal_observation']['value']['sources']['ego_turn_motion.jsonl']='0'*64
        try:audit({DISTANT:forged})
        except ValueError as error:
            require('Fixed safety-only source changed' in str(error), 'Unexpected negative rejection')
            result['negative_changed_motion_rejected']=True
        else:raise ValueError('Changed fixed turn motion was accepted')
    print(json.dumps(result,indent=2))
