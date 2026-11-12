import json
from pathlib import Path
import sys
import tempfile
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from lamp_finalizer import analyze, build_result


def fixture(path, branch='forward_backup_lamp_off'):
    count = 0 if branch == 'no_backup_lamp_installed' else 1
    on = branch == 'forward_backup_lamp_on'
    config = {'law_id': 'NRS-484D-205-4', 'cell_id': 'C111294',
              'actor': 'motor_vehicle_driver', 'case_branch': branch,
              'selected_case_id': 'heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__'+branch,
              'installed_backup_lamp_count': count, 'command_backup_lamp_on': on,
              'rate_hz': 20, 'duration_s': 8, 'frames': 160,
              'ego_blueprint_id': 'vehicle.test', 'other_blueprint_id': 'vehicle.other',
              'equipment_inventory': 'equipment-inventory.json',
              'approach_m': 45, 'exit_m': 35, 'speed_gain': .2,
              'cameras': [{'name': name} for name in ('overview', 'approach',
                  'reference_corner', 'driver_reference')],
              'case': {'recording_description': {'channels': [
                  {'name': name, 'unit': 'source value'} for name in (
                      'native_backup_lamp_on', 'forward_motion_observed',
                      'longitudinal_speed_mps', 'other_vehicle_center_xy_m')]}}}
    (path/'config.json').write_text(json.dumps(config))
    (path/'intersection_context.json').write_text(json.dumps({
        'junction_id': 42,
        'other_vehicle_purpose': 'perpendicular moving intersection context',
        'other_vehicle_priority': 'unresolved pending source review'}))
    (path/'equipment.json').write_text(json.dumps({'kind': 'motor_vehicle',
        'actor_id': 7, 'blueprint_source_sha256': 'fixture-hash',
        'installed_backup_lamps': [{'location':'rear', 'asset_source':'fixture'}]*count}))
    streams = {name: [] for name in ('motion.jsonl', 'video_frames.jsonl',
                                    'other_vehicle.jsonl', 'trace.jsonl')}
    for i in range(4):
        frame, time_s = 100+i, i*.05
        streams['motion.jsonl'].append({'frame': frame, 'time_s': time_s,
            'actor_id': 7, 'heading_xy': [1., 0.], 'velocity_xy_mps': [5., 0.],
            'native_backup_lamp_bit': on})
        streams['video_frames.jsonl'].append({'video_frame': i,
            'carla_frame': frame, 'time_s': time_s})
        streams['other_vehicle.jsonl'].append({'frame': frame, 'time_s': time_s,
            'actor_id': 8, 'center_xy_m': [0., float(i)], 'speed_mps': 4.})
        streams['trace.jsonl'].append({'frame': frame, 'time_s': time_s})
    for name, rows in streams.items():
        (path/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
    return config


class TestLampFinalizer(unittest.TestCase):
    def test_all_exact_cases_from_original_sources(self):
        for branch in ('no_backup_lamp_installed', 'forward_backup_lamp_off',
                       'forward_backup_lamp_on'):
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp); fixture(path, branch)
                report = analyze(path)
                self.assertEqual(len(report['measurements']['backup_lamp_forward']['value']['forward_frames']), 4)
                result = build_result(path, report)
                self.assertFalse(result['setup_confirmed'])
                self.assertFalse(result['maneuver_completed'])
                self.assertEqual(len(result['recording_evidence']), 4)
                with self.assertRaisesRegex(ValueError, 'Retain prior derived'):
                    analyze(path)

    def test_rejects_missing_source_and_changed_other_vehicle_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); fixture(path)
            (path/'other_vehicle.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(path, write_channels=False)
            fixture(path)
            rows = [json.loads(x) for x in (path/'other_vehicle.jsonl').read_text().splitlines()]
            rows[2]['actor_id'] = 9
            (path/'other_vehicle.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
            with self.assertRaisesRegex(ValueError, 'identity missing or changed'):
                analyze(path, write_channels=False)

    def test_rejects_forward_lamp_state_different_from_exact_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); fixture(path, 'forward_backup_lamp_off')
            rows = [json.loads(x) for x in (path/'motion.jsonl').read_text().splitlines()]
            rows[1]['native_backup_lamp_bit'] = True
            (path/'motion.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
            with self.assertRaisesRegex(ValueError, 'lamp-off readback'):
                analyze(path, write_channels=False)


if __name__ == '__main__': unittest.main()
