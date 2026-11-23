"""Five exact comparison protocols and fixed-condition rejection checks."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_case_plan import PAIRS
from comparison_audit import compare
from saved_measurement import measure
from tests.test_saved_measurement import protocol


def measurement(root, suffix):
    root.mkdir()
    site,trace,case_id,_=protocol(root,suffix=suffix)
    output=root/"measurement.json"
    output.write_text(json.dumps(measure(site,trace,case_id)))
    return output


class ComparisonAuditTests(unittest.TestCase):
    def test_all_five_exact_pairs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,(left,right,_) in PAIRS.items():
                first=measurement(root/(name+"-left"),left)
                second=measurement(root/(name+"-right"),right)
                result=compare(first,second,name)
                self.assertTrue(result["passed"])
                self.assertFalse(result["physical_acceptance_claimed"])

    def test_wrong_case_fixed_signal_and_undeclared_metric_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            left=measurement(root/"left","stopped_leftmost_clear")
            right=measurement(root/"right","rolling_leftmost_clear")
            value=json.loads(right.read_text())
            value["case_id"]="wrong-case"
            right.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,"case identity"):
                compare(left,right,"stop_before_turn")
            value["case_id"]=json.loads(left.read_text())["case_id"].replace(
                "stopped_leftmost_clear","rolling_leftmost_clear")
            value["signal_actor_id"]="wrong-signal"
            right.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,"fixed original frame/signal"):
                compare(left,right,"stop_before_turn")
            value["signal_actor_id"]="protocol-signal"
            value["first_approach_lane_id"]="east"
            right.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,"undeclared measured difference"):
                compare(left,right,"stop_before_turn")

    def test_missing_declared_difference_and_changed_fixed_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            left=measurement(root/"left","stopped_leftmost_clear")
            right=measurement(root/"right","rolling_leftmost_clear")
            value=json.loads(right.read_text())
            value["engineering_stop_observed"]=True
            right.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,"declared measured difference absent"):
                compare(left,right,"stop_before_turn")
            value["engineering_stop_observed"]=False
            value["source_hashes"]["opendrive"]="changed"
            right.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,"fixed source changed"):
                compare(left,right,"stop_before_turn")


if __name__=="__main__":
    unittest.main()
