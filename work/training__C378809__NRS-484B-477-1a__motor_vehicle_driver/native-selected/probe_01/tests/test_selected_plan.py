import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("selected_plan", ROOT / "selected_plan.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def diagnostic_survey():
    survey = {key: "diagnostic:" + key for key in module.SOURCE_KEYS}
    survey.update(source_kind="original_native_alley_survey",
                  fixed_cell=module.CELL, ordinance_status="unknown",
                  spawn_xyz_yaw_deg=[0, 0, 0, 0], park_xyz_m=[1, 0, 0],
                  goods_origin_xyz_m=[1, 1, 0],
                  goods_destination_xyz_m=[2, 1, 0],
                  vehicle_blueprint="vehicle.diagnostic",
                  goods_blueprint="static.prop.diagnostic",
                  reviewer="diagnostic-only", reviewed_source_sha256="diagnostic-only")
    return survey


class SelectedPlanTest(unittest.TestCase):
    def test_three_requests_and_isolation(self):
        survey = diagnostic_survey()
        plans = {case: module.plan(case, survey) for case in module.CASES}
        audit = module.compare(plans)
        self.assertEqual(len(audit["case_ids"]), 3)
        self.assertIsNone(audit["legal_result"])
        self.assertFalse(plans[module.ASSIGNMENT + "__probe_02"]["goods_motion_requested"])
        self.assertTrue(plans[module.ASSIGNMENT + "__probe_03"]["idle_after_goods_requested"])

    def test_missing_ordinance_source_rejected(self):
        survey = diagnostic_survey()
        survey.pop("ordinance_status_source_id")
        with self.assertRaisesRegex(ValueError, "missing original source: ordinance_status_source_id"):
            module.plan(next(iter(module.CASES)), survey)

    def test_missing_goods_source_rejected(self):
        survey = diagnostic_survey()
        survey.pop("goods_prop_source_id")
        with self.assertRaisesRegex(ValueError, "missing original source: goods_prop_source_id"):
            module.plan(next(iter(module.CASES)), survey)

    def test_changed_fixed_park_position_rejected(self):
        survey = diagnostic_survey()
        plans = {case: module.plan(case, survey) for case in module.CASES}
        changed = copy.deepcopy(plans)
        changed[module.ASSIGNMENT + "__probe_03"]["fixed_park_xyz_m"] = [2, 0, 0]
        with self.assertRaisesRegex(ValueError, "comparison fixed source changed"):
            module.compare(changed)

    def test_no_legal_cutoff(self):
        survey = diagnostic_survey()
        plans = {case: module.plan(case, survey) for case in module.CASES}
        self.assertTrue(all(plan["expeditiousness"] is None for plan in plans.values()))


if __name__ == "__main__":
    unittest.main()
