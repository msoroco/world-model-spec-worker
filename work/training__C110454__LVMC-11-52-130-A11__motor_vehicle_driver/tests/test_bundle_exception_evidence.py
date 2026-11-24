import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
if not (HERE/'exception_evidence.py').is_file():
    HERE=HERE.parent
spec=importlib.util.spec_from_file_location("exception_evidence",HERE/"exception_evidence.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ExceptionEvidence(unittest.TestCase):
    def inspect_packet(self,packet):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"source.json";path.write_text(json.dumps(packet))
            return module.inspect(path,hashlib.sha256(path.read_bytes()).hexdigest(),packet["branch"])

    def test_three_source_bound_branches(self):
        packets=[
            {"source_kind":"native_context_schema","branch":"necessary_traffic_conflict",
             "other_actor_frames":[100,101],"ego_brake_frames":[101,102],
             "intersection_boundary_source":"native_map_readback","synthetic_fixture":True},
            {"source_kind":"native_context_schema","branch":"compliance_with_law",
             "cited_law_id":"source-citation-probe","cited_law_text_sha256":"a"*64,
             "ego_action_frames":[100],"synthetic_fixture":True},
            {"source_kind":"native_context_schema","branch":"police_or_device_direction",
             "original_pixel_sha256":"b"*64,"direction_source_id":"device-probe",
             "direction_frame":100,"ego_action_frames":[100],"synthetic_fixture":True},
        ]
        for packet in packets:
            with self.subTest(branch=packet["branch"]):
                result=self.inspect_packet(packet)
                self.assertTrue(result["source_packet_complete"])
                self.assertIsNone(result["legal_exception_verdict"])

    def test_missing_original_conflict(self):
        packet={"source_kind":"native_context_schema","branch":"necessary_traffic_conflict",
                "ego_brake_frames":[101],"intersection_boundary_source":"native_map_readback"}
        with self.assertRaisesRegex(ValueError,"Missing original exception source"):
            self.inspect_packet(packet)

    def test_unjoined_direction(self):
        packet={"source_kind":"native_context_schema","branch":"police_or_device_direction",
                "original_pixel_sha256":"b"*64,"direction_source_id":"device-probe",
                "direction_frame":100,"ego_action_frames":[101]}
        with self.assertRaisesRegex(ValueError,"not joined"):
            self.inspect_packet(packet)

    def test_source_tamper(self):
        packet={"source_kind":"native_context_schema","branch":"compliance_with_law",
                "cited_law_id":"probe","cited_law_text_sha256":"a"*64,"ego_action_frames":[100]}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"source.json";path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError,"hash"):
                module.inspect(path,"0"*64,packet["branch"])


if __name__=="__main__":unittest.main()
