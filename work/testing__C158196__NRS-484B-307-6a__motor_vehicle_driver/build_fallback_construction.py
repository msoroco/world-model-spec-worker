"""Build one source-stable physical-risk alternative for an exact yellow/red case."""
import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('entry_before_red', 'entry_at_red', 'entry_after_red', 'stops_on_yellow')
CANDIDATES = ('fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--candidate', choices=CANDIDATES, required=True)
    args = parser.parse_args()
    source = HERE / ('construction.json' if args.case == 'entry_before_red'
                     else f'cases/{args.case}/construction.json')
    construction = deepcopy(json.loads(source.read_text()))
    config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    if config['selected_case_id'] != HERE.name + '__' + args.case:
        raise ValueError('Exact primary case identity changed')
    if config['actor_transforms']['ego']['location']['x'] != -40.0:
        raise ValueError('Primary ego spawn changed')
    if args.candidate == 'fallback1':
        approach = config['camera_mounts']['approach']['pose']
        driver = config['camera_mounts']['driver_reference']['pose']
        approach['location'].update(x=1.5, z=1.9)
        approach['rotation']['pitch'] = -5.0
        driver['location']['z'] = 1.45
        driver['rotation']['pitch'] = -3.0
        trigger = {'source': 'original approach.mkv and driver_reference.mkv source-camera head audit',
                   'metric': 'governing_head_visible_yellow_red_frames',
                   'failure_condition': 'zero visibly identifiable governing-head frames in either forward source'}
        knobs = ['approach camera forward/height/pitch mount',
                 'driver_reference camera height/pitch mount']
    elif args.candidate == 'fallback2':
        x = -44.0 if args.case == 'stops_on_yellow' else -36.0
        config['actor_transforms']['ego']['location']['x'] = x
        trigger = {'source': 'original signal_vehicle_history.jsonl and junction_context.json body/polygon audit',
                   'metric': 'selected_body_entry_timing_or_no_entry_failure',
                   'failure_condition': ('body entered sourced junction polygon at any retained frame'
                                         if args.case == 'stops_on_yellow' else
                                         'first complete-body entry was more than three frames later than the selected red-onset offset')}
        knobs = [f'ego spawn longitudinal x: -40.0 m to {x:.1f} m on the same approach lane']
    else:
        overview = config['camera_mounts']['overview']['pose']
        corner = config['camera_mounts']['reference_corner']['pose']
        overview['location']['z'] = 22.0
        overview['rotation']['pitch'] = -62.0
        corner['location'].update(x=-10.0, y=-9.0, z=10.0)
        corner['rotation'].update(yaw=50.0, pitch=-25.0)
        trigger = {'source': 'original overview.mkv and reference_corner.mkv source-camera head audit',
                   'metric': 'independent_governing_head_visible_frames',
                   'failure_condition': 'zero identifiable governing-head frames in independent fixed-camera views'}
        knobs = ['overview fixed-camera height/pitch mount',
                 'reference_corner fixed-camera position/yaw/pitch mount']
    config_file['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
    relative = Path('cases') / args.case / f'{args.candidate}-construction.json'
    write(HERE / relative, construction)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    case_id = HERE.name + '__' + args.case
    entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
    candidate = {'id': args.candidate, 'construction': str(relative),
                 'construction_sha256': sha(HERE / relative),
                 'trigger': trigger, 'changed_knobs': knobs}
    existing = next((i for i, item in enumerate(entry['candidates'])
                     if item['id'] == args.candidate), None)
    if existing is None:
        entry['candidates'].append(candidate)
    else:
        entry['candidates'][existing].update(candidate)
    entry['candidates'].sort(key=lambda item: item['id'])
    write(manifest_path, manifest)
    print(json.dumps({'case_id': case_id, 'candidate_id': args.candidate,
                      'construction_sha256': candidate['construction_sha256'],
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
