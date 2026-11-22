"""The three planned comparisons must differ in original measured motion."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import audit, PREFIX, PAIRS
from test_uturn_audit import body, multiple_variant, trace


def save(root, name, value):
    path = root / name
    path.write_text(json.dumps(value))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def config(suffix):
    return {"selected_case_id":PREFIX+suffix,"law_id":"NRS-484B-227-1",
            "cell_id":"C126120","actor":"motor_vehicle_driver",
            "rate_hz":20,"duration_s":30,"vehicle_blueprint_id":"vehicle.tesla.model3",
            "cameras":[{"name":"overview","width":1920,"height":1080}]}


class ComparisonAuditTests(unittest.TestCase):
    def pair(self, root, comparison, right):
        left_suffix,right_suffix,_=PAIRS[comparison]
        a=save(root,"left.json",trace())
        b=save(root,"right.json",right)
        c=save(root,"left-config.json",config(left_suffix))
        d=save(root,"right-config.json",config(right_suffix))
        return (comparison,*a,*b,*c,*d)

    def test_all_exact_comparisons_and_fixed_condition_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            closed=copy.deepcopy(trace())
            closed["samples"][2]["body_vertices_xy_m"]=body(1.5,-.5)
            wrong=copy.deepcopy(trace())
            wrong["samples"][-1]["body_vertices_xy_m"]=body(-2,.5)
            for comparison,right in (("continuous_vs_multiple_movement",multiple_variant()),
                                     ("opening_vs_closed_divider",closed),
                                     ("right_roadway_departure",wrong)):
                with self.subTest(comparison=comparison):
                    args=self.pair(root,comparison,right)
                    self.assertEqual(audit(*args)["comparison_id"],comparison)
                    with self.assertRaisesRegex(ValueError,"original source hash mismatch"):
                        audit(*(args[:4]+("wrong hash",)+args[5:]))
                    changed=config(PAIRS[comparison][1]); changed["duration_s"]=31
                    changed_config=save(root,"right-config.json",changed)
                    with self.assertRaisesRegex(ValueError,"fixed comparison config changed"):
                        audit(*(args[:-2]+changed_config))


if __name__ == "__main__":
    unittest.main()
