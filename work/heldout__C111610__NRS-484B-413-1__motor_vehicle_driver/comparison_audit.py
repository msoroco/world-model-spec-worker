"""Independent source-bound audit of the three planned turn comparisons."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IDS = {
    'horn': ROOT.name + '__pedestrian_horn_before_turn',
    'no_horn': ROOT.name + '__pedestrian_no_horn_before_turn',
    'vehicle': ROOT.name + '__other_vehicle_signal_before_turn',
    'both': ROOT.name + '__both_users_both_signals',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inspect(manifest, receipts):
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    require(set(IDS.values()) <= entries.keys(), 'Missing selected turn case')
    records = {}
    for name, case_id in IDS.items():
        entry = entries[case_id]
        require(entry['kind'] == 'delivery' and entry['compatibility']['sha256'], 'Missing source-bound compatibility')
        receipt = receipts[case_id]
        require(receipt['passed'] and receipt['case_id'] == case_id, 'Wrong or failed compatibility receipt')
        require(receipt['construction_sha256'] == entry['construction_sha256'], 'Stale construction binding')
        value = receipt['measurement_examples']['turn_signal_observation']['value']
        require(value['format'] == 'worker-turn-signal-observation', 'Wrong measured turn format')
        require(value['sources'].get('ego_turn_motion.jsonl') and value['sources'].get('ego_signal_audio.jsonl'), 'Missing original motion or signal source')
        construction = json.loads((ROOT / entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
        require(config['selected_case_id'] == case_id, 'Wrong exact construction config')
        records[name] = (config, value)
    baseline_config, baseline = records['horn']
    for name, (config, value) in records.items():
        for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s', 'cameras', 'engineering'):
            require(config[key] == baseline_config[key], f'{name}: fixed condition {key} changed')
        require(value['sources']['ego_turn_motion.jsonl'] == baseline['sources']['ego_turn_motion.jsonl'], f'{name}: direct-course turn source changed')
        require(value['turn_onset_frame'] == baseline['turn_onset_frame'], f'{name}: turn onset changed')
        require(value['turn_direction'] == baseline['turn_direction'], f'{name}: turn direction changed')
    no_horn = records['no_horn'][1]
    vehicle = records['vehicle'][1]
    both = records['both'][1]
    require(baseline['pedestrian_may_be_affected'] and no_horn['pedestrian_may_be_affected'], 'Pedestrian comparison lacks pedestrian')
    require(baseline['sources']['affected_participants.json'] == no_horn['sources']['affected_participants.json'], 'Pedestrian context changed with horn')
    require(baseline['max_pre_turn_listener_audio_rms'] > no_horn['max_pre_turn_listener_audio_rms'] == 0, 'Horn contrast absent in source measurement')
    require(baseline['sources']['ego_signal_audio.jsonl'] != no_horn['sources']['ego_signal_audio.jsonl'], 'Horn source unchanged')
    require(not vehicle['pedestrian_may_be_affected'] and vehicle['vehicle_may_be_affected'], 'Other-vehicle branch absent')
    require(vehicle['pre_turn_indicator_frames'], 'Other-vehicle signal branch lacks pre-turn readback')
    require(both['pedestrian_may_be_affected'] and both['vehicle_may_be_affected'], 'Combined-user duties absent')
    require(both['pre_turn_indicator_frames'] and both['max_pre_turn_listener_audio_rms'] > 0, 'Combined signals absent')
    return {'format': 'worker-turn-comparison-audit', 'passed': True,
            'comparison_ids': ['pedestrian_horn_timing', 'affected_user_branch', 'combined_user_duties'],
            'case_ids': list(IDS.values()), 'scope': 'source-shaped CPU comparison only; no physical or legal finding'}


def load():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    receipts = {}
    for entry in manifest['cases']:
        if entry['case_id'] in IDS.values():
            receipts[entry['case_id']] = json.loads((ROOT / entry['compatibility']['receipt']).read_text())
    return manifest, receipts


if __name__ == '__main__':
    manifest, receipts = load()
    print(json.dumps(inspect(manifest, receipts), indent=2))
