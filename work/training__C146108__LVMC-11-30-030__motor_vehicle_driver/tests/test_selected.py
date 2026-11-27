import unittest
from crosswalk_pass_scene import CASES, request, validate
from measure_crosswalk_pass import measure
from prove_crosswalk_pass import context, trace
from runner import check


class SelectedCrosswalkTests(unittest.TestCase):
    def test_native_source_requests(self):
        self.assertEqual(len(check()["case_ids"]), 4)
        for slug in CASES:
            self.assertTrue(validate(request(slug))["authored_request_checked"])

    def test_controlled_source_trace(self):
        for slug in CASES:
            kind = "unmarked_intersection" if slug.startswith("unmarked_") else "marked"
            measured = measure(context(kind), trace(slug))
            self.assertEqual(measured["pass_observed"], slug.endswith("true"))
            self.assertEqual(measured["legal_compliance"], "unassessed")

    def test_missing_stop_purpose_rejected(self):
        source = context()
        source["lead_stopped_for_pedestrian_sourced"] = False
        with self.assertRaisesRegex(ValueError, "Purpose"):
            measure(source, trace("true"))


if __name__ == "__main__":
    unittest.main()
