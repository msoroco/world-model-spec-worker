"""Independent source-bound comparison of the two affected-vehicle placements."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.name + '__vehicle_clearance_near_before_turn'
NEW = ROOT.name + '__vehicle_clearance_far_before_turn'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(manifest=None, receipts=None):
    if manifest is None:
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entries = {item['case_id']: item for item in manifest['cases']}
    require(OLD in entries and NEW in entries, 'Missing vehicle clearance exact case')
    sources = {}
    for case_id in (OLD, NEW):
        entry = entries[case_id]
        receipt_path = ROOT / entry['compatibility']['receipt']
        receipt = (receipts or {}).get(case_id) or json.loads(receipt_path.read_text())
        require(sha256(receipt_path.read_bytes()).hexdigest() == entry['compatibility']['sha256'],
                'Stale vehicle clearance receipt')
        require(receipt['passed'] and receipt['case_id'] == case_id
                and receipt['construction_sha256'] == entry['construction_sha256'],
                'Wrong vehicle clearance receipt or construction')
        construction_path = ROOT / entry['construction']
        require(sha256(construction_path.read_bytes()).hexdigest() == entry['construction_sha256'],
                'Stale vehicle clearance construction')
        construction = json.loads(construction_path.read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        require(config['selected_case_id'] == case_id, 'Wrong vehicle clearance identity')
        value = receipt['measurement_examples']['turn_signal_observation']['value']
        require(value['format'] == 'worker-turn-signal-observation', 'Wrong turn measurement')
        sources[case_id] = config, value
    base_config, base = sources[OLD]
    near_config, near = sources[NEW]
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s', 'cameras'):
        require(base_config[key] == near_config[key], 'Vehicle clearance fixed condition changed: ' + key)
    fixed_near = dict(base_config['engineering'])
    fixed_far = dict(near_config['engineering'])
    require(fixed_near.pop('vehicle_along_m') == fixed_far.pop('vehicle_along_m') == 5.0
            and fixed_near.pop('vehicle_left_m') == 2.0
            and fixed_far.pop('vehicle_left_m') == 14.0,
            'Vehicle placement control differs from the selected construction')
    require(fixed_near == fixed_far, 'Other route or controller control changed')
    for key in ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl', 'affected_participants.json'):
        require(base['sources'][key] == near['sources'][key], 'Fixed original source changed: ' + key)
    require(base['sources']['participant_bodies.jsonl'] != near['sources']['participant_bodies.jsonl'],
            'Vehicle body source did not change')
    require(base['turn_onset_frame'] == near['turn_onset_frame']
            and base['turn_direction'] == near['turn_direction'], 'Turn onset or direction changed')
    base_gap = base['participant_clearance']['affected_vehicle']['minimum_sampled_surface_gap_m']
    near_gap = near['participant_clearance']['affected_vehicle']['minimum_sampled_surface_gap_m']
    require(base_gap != near_gap, 'Vehicle clearance measurement did not change')
    require(base['participant_clearance']['ped_listener'] == near['participant_clearance']['ped_listener'],
            'Pedestrian geometry changed with vehicle placement')
    return {'format': 'worker-vehicle-clearance-comparison-audit', 'passed': True,
            'comparison_id': 'vehicle_clearance_sweep', 'case_ids': [OLD, NEW],
            'minimum_sampled_surface_gap_m': [base_gap, near_gap],
            'scope': 'source-shaped CPU comparison; affectedness and safety are unjudged'}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
