"""Probe where the authored gap grid separates controller commands.

These are independent synthetic actor states, not a Native motion trace or a
claim that any requested body gap is physically feasible.
"""
import argparse
import hashlib
import json
import copy
from pathlib import Path
from types import SimpleNamespace

from following_controller import FollowingController
from sweep_probe import Actor, GRID_M


SPACINGS_M = (8.0, 10.0, 12.0, 13.0, 14.0, 16.0, 20.0)
LEAD_SPEEDS_MPS = (2.5, 3.5, 5.0)
PHASES = (('before_lane_change', 0.0), ('after_lane_change', 75.0))


def build_capture_candidate(output):
    """Stage an exact, CPU-checkable capture construction without selecting it.

    The existing nine-case manifest and its receipts remain bound to their
    original bytes until the full replacement proof chain has passed.
    """
    root = Path(__file__).resolve().parent
    repo = root.parents[1]
    source = json.loads((root / 'execution-manifest.json').read_text())
    if len(source['cases']) != 9:
        raise ValueError('Nine-case source manifest required')
    controller = (root / 'following_controller.py').read_text()
    old = '                 lead_brake_start_m=None):'
    new = '                 lead_brake_start_m=None, minimum_following_frames=40, unbraked_lead=False):'
    if controller.count(old) != 1:
        raise ValueError('Controller constructor anchor changed')
    controller = controller.replace(old, new)
    old = '        self.brake_start=lead_brake_start_m\n'
    new = (old + "        if type(minimum_following_frames) is not int or minimum_following_frames<0:\n"
           "            raise ValueError('Invalid minimum following frames')\n"
           "        if type(unbraked_lead) is not bool:raise ValueError('Invalid lead brake policy')\n"
           '        self.minimum_following_frames=minimum_following_frames\n'
           '        self.unbraked_lead=unbraked_lead\n'
           '        self.step_count=0\n')
    if controller.count(old) != 1:
        raise ValueError('Controller state anchor changed')
    controller = controller.replace(old, new)
    old = '        lane_change_started=progress>=self.start\n'
    new = '        lane_change_started=progress>=self.start and self.step_count>=self.minimum_following_frames\n'
    if controller.count(old) != 1:
        raise ValueError('Lane-change anchor changed')
    controller = controller.replace(old, new)
    old = '        lead_brake=min(1.0,max(0.0,-0.3*lead_error))\n'
    new = '        lead_brake=0.0 if self.unbraked_lead else min(1.0,max(0.0,-0.3*lead_error))\n'
    if controller.count(old) != 1:
        raise ValueError('Lead brake anchor changed')
    controller = controller.replace(old, new)
    old = '        lead.apply_control(_control(self.factory,lead_throttle,lead_brake))\n'
    new = old + '        self.step_count+=1\n'
    if controller.count(old) != 1:
        raise ValueError('Step counter anchor changed')
    controller = controller.replace(old, new)

    manifest = copy.deepcopy(source)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name in ('case-plan.json', 'measurement-contract.json'):
        (output / name).write_bytes((root / name).read_bytes())
    (output / 'proposals').mkdir(exist_ok=True)
    (output / 'proposals/cases.json').write_bytes((root / 'proposals/cases.json').read_bytes())
    changed = []
    for case in manifest['cases']:
        case_name = case['case_id'].rsplit('source_verified_', 1)[-1]
        for candidate, row in [('primary', case), *[(x['id'], x) for x in case['candidates']]]:
            bundle = json.loads((root / row['construction']).read_text())
            files = {f['path']: f for f in bundle['files']}
            if 'runner.py' not in files or 'following_controller.py' not in files:
                raise ValueError('Capture sources missing: ' + case_name)
            runner = files['runner.py']['content']
            if case_name == 'lead_brakes':
                old = "                lead_brake_start_m=route['corridor_length_m']*config['lead_brake_start_fraction'])"
                new = ("                lead_brake_start_m=route['corridor_length_m']*config['lead_brake_start_fraction'],\n"
                       "                minimum_following_frames=40, unbraked_lead=False)")
            else:
                old = "                lead_speed_mps=config['lead_target_speed_mps'])"
                new = ("                lead_speed_mps=config['lead_target_speed_mps'],\n"
                       "                minimum_following_frames=40, unbraked_lead=True)")
            if runner.count(old) == 1:
                runner = runner.replace(old, new)
            elif runner.count(new) != 1:
                raise ValueError('Runner controller anchor changed: ' + case_name)
            files['runner.py']['content'] = runner
            files['runner.py'].pop('source', None)
            files['following_controller.py']['content'] = controller
            files['following_controller.py'].pop('source', None)
            target = output / (case_name + '-' + candidate + '.json')
            target.write_text(json.dumps(bundle, indent=2) + '\n')
            row['construction'] = target.name
            row['construction_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
            for stale in ('offline', 'compatibility', 'post_capture'):
                row.pop(stale, None)
            changed.append({'case_id': case['case_id'], 'candidate_id': candidate,
                            'construction': row['construction'], 'sha256': row['construction_sha256']})
        for stale in ('physical_preparation', 'delivery_acceptance', 'negative'):
            case.pop(stale, None)
    (output / 'candidate-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'candidate-index.json').write_text(json.dumps({
        'format': 'c101303-fixed-following-capture-candidate',
        'selected': False, 'native_realization_passed': False,
        'minimum_following_frames': 40, 'unbraked_lead_except_braking_case': True,
        'source_manifest_sha256': hashlib.sha256((root / 'execution-manifest.json').read_bytes()).hexdigest(),
        'constructions': changed}, indent=2) + '\n')
    return len(changed)


def probe(config):
    if (config['requested_engineering_gap_m'] != 10.0 or
            config['minimum_corridor_length_m'] != 100.0 or
            config['ego_target_speed_mps'] != 4.0):
        raise ValueError('Envelope requires the reviewed base engineering configuration')
    rows = []
    for phase, progress in PHASES:
        for lead_speed in LEAD_SPEEDS_MPS:
            for spacing in SPACINGS_M:
                commands = []
                for gap in GRID_M:
                    ego, lead = Actor(progress, 4.0), Actor(progress + spacing, lead_speed)
                    controller = FollowingController(
                        SimpleNamespace, target_speed_mps=config['ego_target_speed_mps'],
                        target_center_spacing_m=gap + 4.0,
                        lane_change_start_m=55.0, lane_change_end_m=70.0,
                        lead_speed_mps=config['lead_target_speed_mps'])
                    state = controller.step(ego, lead,
                        route_origin_xyz=(0.0, 0.0, 0.0), route_forward_xy=(1.0, 0.0),
                        target_lane_center_xy=(0.0, 3.5))
                    commands.append(state['requested_engineering_speed_mps'])
                if not commands[0] >= commands[1] >= commands[2]:
                    raise ValueError('Controller reversed the gap-grid command order')
                rows.append({'phase': phase, 'route_progress_m': progress,
                             'center_spacing_m': spacing, 'lead_speed_mps': lead_speed,
                             'requested_speed_mps_by_gap': commands,
                             'all_three_distinct': commands[0] > commands[1] > commands[2]})
    if not any(row['all_three_distinct'] for row in rows):
        raise ValueError('No synthetic actor state separates the gap grid')
    return {'format': 'c101303-controller-envelope-probe', 'diagnostic_only': True,
            'physical_feasibility_proven': False, 'legal_threshold_asserted': False,
            'requested_gap_grid_m': list(GRID_M),
            'fixed_ego_speed_mps': 4.0, 'states': rows,
            'distinct_state_count': sum(row['all_three_distinct'] for row in rows),
            'state_count': len(rows),
            'interpretation': 'Controller command separability across independently supplied synthetic states; no dynamics, complete-body geometry, or realized spacing.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--build-capture-candidate', type=Path)
    args = parser.parse_args()
    if args.build_capture_candidate:
        print(json.dumps({'staged_constructions': build_capture_candidate(args.build_capture_candidate),
                          'selected': False, 'native_realization_passed': False}))
        return
    if not args.config or not args.output:
        parser.error('--config and --output required for envelope probe')
    result = probe(json.loads(args.config.read_text()))
    result['sources'] = {name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                         for name, path in (('config', args.config),
                            ('controller', Path(__file__).with_name('following_controller.py')),
                            ('grid', Path(__file__).with_name('sweep_probe.py')),
                            ('envelope', Path(__file__)))}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'format': result['format'], 'state_count': result['state_count'],
                      'distinct_state_count': result['distinct_state_count'],
                      'physical_feasibility_proven': False,
                      'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
