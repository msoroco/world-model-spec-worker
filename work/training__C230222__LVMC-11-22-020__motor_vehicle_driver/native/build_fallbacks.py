"""Make exact-case source-triggered Native fallback control schedules."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / 'draft-selected-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for label in ('probe_a', 'probe_b'):
        case_id = ROOT.name + '__' + label
        entry = next(row for row in manifest['cases'] if row['case_id'] == case_id)
        primary = json.loads((ROOT / entry['construction']).read_text())
        fallback = json.loads(json.dumps(primary))
        config_file = next(item for item in fallback['files'] if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        config['candidate_id'] = 'fallback1'
        if label == 'probe_a':
            config['control_phases'][0]['throttle'] = 0.18
            config['control_phases'][1]['throttle'] = 0.14
            config['control_phases'][2]['throttle'] = 0.08
            knobs = ['Lower approach, curbside and departure throttle requests to reduce Native pedestrian proximity if primary exceeds the engineering proximity trigger.']
            trigger = {'source': 'native-body-geometry.jsonl',
                       'metric': 'minimum planar pedestrian body gap during curbside travel',
                       'failure_condition': 'Primary Native body gap falls below the one-metre engineering camera/recovery margin, or the walker leaves the four-view field of view.'}
        else:
            config['control_phases'][1]['steer'] = 0.18
            config['control_phases'][1]['throttle'] = 0.12
            knobs = ['Increase requested curbside steering amplitude and reduce throttle so original yaw and separation can be observed if the primary path remains nearly straight.']
            trigger = {'source': 'native-ego-frames.jsonl',
                       'metric': 'original Native curbside yaw-rate excursion',
                       'failure_condition': 'Primary measured yaw-rate excursion is indistinguishable from probe_a in source-joined samples, or the route leaves the observed curbside lane.'}
        config_file['content'] = json.dumps(config, indent=2) + '\n'
        fallback['measurement_plan'] += ' Fallback1 changes controller requests only after the stated source trigger; neither request establishes a legal verdict.'
        path = ROOT / 'draft-native' / label / 'fallback1/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, indent=2) + '\n')
        entry['candidates'] = [{'id': 'fallback1',
                                'construction': str(path.relative_to(ROOT)),
                                'construction_sha256': sha(path),
                                'trigger': trigger, 'changed_knobs': knobs}]
        print(label, sha(path))
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
