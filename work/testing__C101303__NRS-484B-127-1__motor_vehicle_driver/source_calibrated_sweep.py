"""Source-calibrated CPU response probe for the following-gap engineering grid.

The actor dynamics below are a simple diagnostic model, never Native motion.
The body offset comes from sealed full-duration diagnostic body histories.
"""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from following_controller import FollowingController
from prove_body_gap_geometry import source_offsets
from sweep_dynamics_probe import Actor, RATE_HZ, FRAMES
from sweep_probe import GRID_M


FOLDER = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_runner(manifest, case_suffix):
    matches = [case for case in manifest['cases'] if case['case_id'].endswith(case_suffix)]
    if len(matches) != 1:
        raise ValueError('Selected case missing or duplicated: ' + case_suffix)
    case = matches[0]
    path = FOLDER / case['construction']
    if sha(path) != case['construction_sha256']:
        raise ValueError('Selected construction hash changed: ' + case_suffix)
    bundle = json.loads(path.read_text())
    runner = next(item['content'] for item in bundle['files'] if item['path'] == 'runner.py')
    if ('from body_gap_geometry import native_body_offset' not in runner or
            "target_center_spacing_m=config['requested_engineering_gap_m']+native_body_offset(" not in runner):
        raise ValueError('Selected runner does not derive center spacing from Native bodies')
    return {'case_id': case['case_id'], 'construction': case['construction'],
            'construction_sha256': sha(path)}


def trajectory(config, requested_gap_m, body_offset_m):
    ego, lead = Actor(0, 4.0), Actor(13.0, 3.5)
    controller = FollowingController(
        SimpleNamespace, target_speed_mps=config['ego_target_speed_mps'],
        target_center_spacing_m=requested_gap_m + body_offset_m,
        lane_change_start_m=55.0, lane_change_end_m=70.0,
        lead_speed_mps=config['lead_target_speed_mps'])
    following = []
    commanded = 0
    for frame in range(FRAMES):
        state = controller.step(ego, lead,
            route_origin_xyz=(0.0, 0.0, 0.0), route_forward_xy=(1.0, 0.0),
            target_lane_center_xy=(0.0, 3.5))
        if state['route_progress_m'] < 55.0:
            following.append(state['measured_center_spacing_m'] - body_offset_m)
            commanded += state['requested_engineering_speed_mps'] == 0
        ego.advance()
        lead.advance()
    if not following or min(following) <= 0:
        raise ValueError('Synthetic trajectory lacks positive pre-change body separation')
    return {'requested_engineering_gap_m': requested_gap_m,
            'target_center_spacing_m': controller.target_spacing,
            'frames': FRAMES, 'pre_change_frames': len(following),
            'first_pre_change_body_gap_m': following[0],
            'minimum_pre_change_body_gap_m': min(following),
            'mean_pre_change_body_gap_m': sum(following) / len(following),
            'last_pre_change_body_gap_m': following[-1],
            'zero_command_frames_before_change': commanded,
            'final_ego_position_m': ego.x, 'final_lead_position_m': lead.x}


def probe(config_path, manifest_path, base_root, closer_root):
    config = json.loads(config_path.read_text())
    if (config.get('requested_engineering_gap_m') != 10.0 or
            config.get('ego_target_speed_mps') != 4.0 or
            config.get('lead_target_speed_mps') != 3.5 or
            config.get('rate_hz') != RATE_HZ or config.get('duration_s') != 45):
        raise ValueError('Reviewed base engineering configuration required')
    manifest = json.loads(manifest_path.read_text())
    selections = [selected_runner(manifest, suffix) for suffix in
                  ('__source_verified_base', '__source_verified_closer')]
    sources = [source_offsets(root) for root in (base_root, closer_root)]
    if [source['requested_gap_m'] for source in sources] != [10.0, 7.0]:
        raise ValueError('Sealed base/closer gap identities changed')
    offsets = [source['projected_body_offset_m'] for source in sources]
    if any(abs(value - 2.0) > 1e-6 for value in offsets):
        raise ValueError('Sealed diagnostic body offset changed')
    offset = offsets[0]
    points = [trajectory(config, gap, offset) for gap in GRID_M]
    if [point['target_center_spacing_m'] for point in points] != [9.0, 10.5, 12.0]:
        raise ValueError('Source-calibrated grid spacing changed')
    return {
        'format': 'c101303-source-calibrated-cpu-sweep',
        'diagnostic_only': True, 'physical_feasibility_proven': False,
        'legal_threshold_asserted': False,
        'frames': FRAMES, 'rate_hz': RATE_HZ,
        'projected_body_offset_m': offset,
        'selected_constructions': selections,
        'sealed_diagnostic_sources': sources,
        'points': points,
        'model': {'throttle_acceleration_mps2': 2.5,
                  'brake_deceleration_mps2': 5.0, 'speed_drag_per_s': 0.05,
                  'initial_ego_speed_mps': 4.0, 'initial_lead_speed_mps': 3.5,
                  'initial_center_spacing_m': 13.0},
        'limitations': [
            'The sealed 900-frame histories and this response model are synthetic diagnostics.',
            'No selected hill-crest Native motion, body dimensions, or sight lines were measured.',
            'Original accepted Native actor traces are not present in the export.',
            'Reasonable and prudent following has no numeric legal cutoff in the assigned text.'],
        'source_sha256': {name: sha(path) for name, path in
                          (('config', config_path), ('manifest', manifest_path),
                           ('controller', FOLDER / 'following_controller.py'),
                           ('body_helper', FOLDER / 'body_gap_geometry.py'),
                           ('source_reader', FOLDER / 'prove_body_gap_geometry.py'),
                           ('grid', FOLDER / 'sweep_probe.py'),
                           ('dynamics_model', FOLDER / 'sweep_dynamics_probe.py'),
                           ('probe', Path(__file__)))}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--base-root', type=Path, required=True)
    parser.add_argument('--closer-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.config, args.manifest, args.base_root, args.closer_root)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'format': result['format'], 'points': result['points'],
                      'physical_feasibility_proven': False,
                      'output_sha256': sha(args.output)}, sort_keys=True))


if __name__ == '__main__':
    main()
