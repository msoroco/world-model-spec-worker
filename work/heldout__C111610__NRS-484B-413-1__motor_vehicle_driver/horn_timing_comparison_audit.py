"""Independently compare fixed turn sources and deliberate horn request timing."""
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
EARLY = ROOT.name + '__pedestrian_horn_before_turn'
LATE = ROOT.name + '__pedestrian_horn_after_onset'


def require(value, message):
    if not value:
        raise ValueError(message)


def audit(receipts=None):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entries = {item['case_id']: item for item in manifest['cases']}
    require(EARLY in entries and LATE in entries, 'Missing exact horn timing cases')
    values = {}
    for case in (EARLY, LATE):
        entry = entries[case]
        receipt_path = ROOT / entry['compatibility']['receipt']
        require(sha256(receipt_path.read_bytes()).hexdigest() == entry['compatibility']['sha256'],
                'Stale horn timing receipt')
        receipt = (receipts or {}).get(case) or json.loads(receipt_path.read_text())
        require(receipt['passed'] and receipt['case_id'] == case and
                receipt['construction_sha256'] == entry['construction_sha256'],
                'Wrong horn timing receipt or construction')
        construction_path = ROOT / entry['construction']
        require(sha256(construction_path.read_bytes()).hexdigest() == entry['construction_sha256'],
                'Stale horn timing construction')
        construction = json.loads(construction_path.read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        require(config['selected_case_id'] == case, 'Wrong horn timing identity')
        observation = receipt['measurement_examples']['turn_signal_observation']['value']
        require(observation['format'] == 'worker-turn-signal-observation',
                'Wrong horn timing measurement')
        values[case] = config, observation, receipt
    early_config, early, early_receipt = values[EARLY]
    late_config, late, late_receipt = values[LATE]
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
                'cameras', 'required_atoms', 'source_packets'):
        require(early_config[key] == late_config[key], 'Fixed horn timing condition changed: ' + key)
    early_engineering = dict(early_config['engineering'])
    late_engineering = dict(late_config['engineering'])
    require(early_engineering.pop('horn_request_frame', 20) == 20 and
            late_engineering.pop('horn_request_frame', None) == 120,
            'Horn request control does not match selected constructions')
    require(early_engineering == late_engineering, 'Turn or participant control changed')
    for key in ('ego_turn_motion.jsonl', 'participant_bodies.jsonl', 'affected_participants.json'):
        require(early['sources'][key] == late['sources'][key],
                'Fixed original horn timing source changed: ' + key)
    for key in ('ego_signal_audio.jsonl',):
        require(early['sources'][key] != late['sources'][key],
                'Deliberate original horn timing source did not change: ' + key)
    for key in ('listener_audio_original.jsonl', 'horn_actuation.jsonl'):
        require(early_receipt['fixture_manifest'][key] != late_receipt['fixture_manifest'][key],
                'Deliberate original horn timing source did not change: ' + key)
    require(early['turn_onset_frame'] == late['turn_onset_frame'] and
            early['turn_direction'] == late['turn_direction'], 'Turn onset or direction changed')
    require(early['max_pre_turn_listener_audio_rms'] > late['max_pre_turn_listener_audio_rms'] == 0.0,
            'Measured pre-turn listener contrast absent')
    return {'format': 'worker-horn-timing-comparison-audit', 'passed': True,
            'comparison_id': 'horn_request_timing_sweep', 'case_ids': [EARLY, LATE],
            'pre_turn_listener_rms': [early['max_pre_turn_listener_audio_rms'],
                                      late['max_pre_turn_listener_audio_rms']],
            'scope': 'source-shaped CPU comparison; emission, audibility, effect and safety unjudged'}


if __name__ == '__main__':
    result = audit()
    if '--selftest' in sys.argv:
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        late = next(item for item in manifest['cases'] if item['case_id'] == LATE)
        forged = json.loads((ROOT / late['compatibility']['receipt']).read_text())
        forged['measurement_examples']['turn_signal_observation']['value']['sources']['ego_turn_motion.jsonl'] = '0' * 64
        try:
            audit({LATE: forged})
        except ValueError as error:
            require('Fixed original horn timing source changed' in str(error),
                    'Unexpected horn timing negative rejection')
            result['negative_fixed_motion_rejected'] = True
        else:
            raise ValueError('Changed fixed motion source was accepted')
    print(json.dumps(result, indent=2))
