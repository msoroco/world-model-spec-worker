"""CPU checks for the separate no-device delivery construction and audit."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from audit_device_delivery import audit

HERE = Path(__file__).resolve().parents[1]
FILES = ('site.json', 'construction.json',
         'stop_ego_left_near_time-selected-compatibility.json',
         'stop_ego_left_near_time-selected-analysis.log',
         'stop_ego_left_near_time-selected-negative.log',
         'stop_ego_left_near_time-selected-processing.json',
         'absent-site.json', 'absent-construction.json',
         'absent-review/sign_governance_source.json',
         'absent-review/sign_face_video_source.json',
         'stop_ego_left_near_time_no_device-selected-compatibility.json',
         'stop_ego_left_near_time_no_device-selected-analysis.log',
         'stop_ego_left_near_time_no_device-selected-negative.log',
         'stop_ego_left_near_time_no_device-selected-processing.json')


def control_module():
    path = HERE / 'absent-median_route_control.py'
    spec = importlib.util.spec_from_file_location('absent_control', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AbsentDeviceCaseTests(unittest.TestCase):
    def test_absent_scene_and_present_device_rejection(self):
        scene = json.loads((HERE / 'absent-site.json').read_text())
        control = control_module()
        self.assertIs(control.validate_scene(scene), scene)
        scene['stop_sign'] = {'native_id': 17, 'governed_lane_id': 'eastbound'}
        with self.assertRaisesRegex(ValueError, 'empty ego entrance'):
            control.validate_scene(scene)

    def test_pair_audit_rejects_changed_fixed_route_and_false_claim(self):
        report = audit(HERE)
        self.assertTrue(report['recorded_only_passed'])
        self.assertFalse(report['physical_acceptance_claimed'])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / HERE.name
            root.mkdir()
            for name in FILES:
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(HERE / name, destination)
            site = root / 'absent-site.json'
            data = json.loads(site.read_text())
            data['approaches']['other']['route_xy_m'][-1] = [0, 0]
            site.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'site binding'):
                audit(root)
            shutil.copyfile(HERE / 'absent-site.json', site)
            saved = root / 'stop_ego_left_near_time_no_device-selected-processing.json'
            data = json.loads(saved.read_text())
            data['physical_acceptance_claimed'] = True
            saved.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'saved-source'):
                audit(root)


if __name__ == '__main__':
    unittest.main()
