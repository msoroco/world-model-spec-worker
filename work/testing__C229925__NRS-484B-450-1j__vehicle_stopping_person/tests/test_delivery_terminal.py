import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('delivery_audit', ROOT / 'delivery_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def history():
    records = []
    for index in range(900):
        center_x = 10 if index >= 860 else 10 * index / 860
        vertices = [[center_x + x, -5 + y, z]
                    for x in (-.5, .5) for y in (-.4, .4) for z in (0, 1)]
        records.append(dict(vehicle_vertices=vertices,
                            speed_mps=0 if index >= 860 else .5,
                            control_state='stop', control_request={},
                            traffic_vehicle_id=None, traffic_speed_mps=None))
    return records


class TerminalHaltTests(unittest.TestCase):
    def setUp(self):
        self.scene = dict(vehicle_target_xy=[10, -5], road_forward_xy=[1, 0],
                          road_origin_xy=[0, 0], entrance_start_xy=[10, 5])
        self.case = SimpleNamespace(side='opposite', activity='stop',
                                    circumstance='ordinary')

    def test_complete_original_halt(self):
        receipt = audit.terminal_halt(history(), self.scene, self.case)
        self.assertEqual(receipt['tail_frames'], 40)
        self.assertFalse(receipt['legal_distance_or_exception_decided'])

    def test_terminal_body_away_from_target_rejected(self):
        records = history()
        records[-1]['vehicle_vertices'] = [[x + 2, y, z] for x, y, z in
                                          records[-1]['vehicle_vertices']]
        with self.assertRaisesRegex(ValueError, 'designed halt'):
            audit.terminal_halt(records, self.scene, self.case)

    def test_traffic_conflict_without_original_motion_rejected(self):
        self.case.circumstance = 'traffic_conflict'
        with self.assertRaisesRegex(ValueError, 'conflicting traffic motion absent'):
            audit.terminal_halt(history(), self.scene, self.case)


if __name__ == '__main__':
    unittest.main()
