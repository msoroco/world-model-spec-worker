"""Add source-measured alternatives and exception prompts to both mounted bundles."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

ADDITIONAL = {
    'ru.electric_bicycle': 'Native machine class and original body pixels distinguish the selected bicycle from an electric bicycle.',
    'ru.electric_scooter': 'Native machine class and original body pixels distinguish the selected bicycle from an electric scooter.',
    'drv.turning': 'Saved rider and Native heading history identify whether a turn was attempted.',
    'ru.pedestrian': 'Rider posture and walking-machine source rows locate the potential dismount exception.',
    'kin.speed': 'Saved original trace velocity measures walking speed without a statutory cutoff.',
}


def main():
    path = HERE / 'draft-thirty-second-mounted-turn-primary-construction.json'
    construction = json.loads(path.read_text())
    description = construction['recording_description']
    existing = {c['name'] for c in description['channels']}
    for name, method in ADDITIONAL.items():
        if name not in existing:
            description['channels'].append({
                'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                'method': method, 'time_window': 'entire 30 s / 600-frame attempt',
                'reference_frame': 'Native map and original camera frame',
                'uncertainty': '50 ms sampling; original posture and machine pixels require review',
            })
    for part in construction['files']:
        if part['path'] == 'engineering.py':
            part['content'] = (HERE / 'native/engineering.py').read_text()
        if part['path'] == 'runner.py':
            part['content'] = (HERE / 'native/runner.py').read_text()
        if part['path'] == 'finalize.py':
            part['content'] = (HERE / 'native/finalize.py').read_text()
        if part['path'] == 'config.json':
            config = json.loads(part['content'])
            config['recording_description'] = description
            config['source_packets'] = ['scenario_geometry', 'scenario_rule_evidence']
            config['required_atoms'] = [atom for atom in config['required_atoms']
                                        if atom not in ('ru.rider_posture', 'drv.u_turn', 'drv.turning')]
            part['content'] = json.dumps(config, indent=2) + '\n'
    path.write_text(json.dumps(construction, indent=2, sort_keys=True) + '\n')
    print(path)


if __name__ == '__main__':
    main()
