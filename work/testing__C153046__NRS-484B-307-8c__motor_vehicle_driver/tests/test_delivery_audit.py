"""Diagnostic protocol for the independent original delivery verifier."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_case_plan import KINDS
from independent.delivery_audit import PINNED_MEDIA, CAMERAS, sha, verify
from saved_measurement import measure
from tests.test_saved_measurement import protocol


def attempt(root, suffix):
    root.mkdir()
    site,trace,case_id,rows=protocol(root,suffix=suffix)
    measurement=root/"measurement.json"
    measurement.write_text(json.dumps(measure(site,trace,case_id)))
    mapping=root/"frame-map.jsonl"
    mapping.write_text("".join(json.dumps({"video_frame":index,
             "native_frame":row["native_frame"]["frame"],
             "time_s":row["native_frame"]["time_s"]})+"\n"
             for index,row in enumerate(rows)))
    (root/"raw.mkv").write_text("synthetic protocol composed video\n")
    for name in CAMERAS:
        (root/name).write_text("synthetic protocol camera "+name+"\n")
    (root/"result.json").write_text(json.dumps({"case_id":case_id,
       "provenance_kind":"native","diagnostic_fixture":True,
       "setup_confirmed":True,"maneuver_completed":True,
       "measurement_sha256":sha(measurement),
       "physical_checks":{"setup":"met","maneuver":"met"}}))
    (root/"source-decode.json").write_text(json.dumps({"format":"source-decode",
       "passed":True,"auditor_path":str(PINNED_MEDIA),
       "auditor_sha256":sha(PINNED_MEDIA),"video_sha256":sha(root/"raw.mkv"),
       "mapping_sha256":sha(mapping),"frames":len(rows),
       "checks":{"frame_count":"all-decoded-frames"}}))
    (root/"composition.json").write_text(json.dumps({"format":"synchronized-four-view",
       "frames":len(rows),"frame_map_sha256":sha(mapping),
       "primary_sha256":sha(root/"raw.mkv"),
       "sources":{name.removesuffix(".mkv"):sha(root/name) for name in CAMERAS}}))
    observed={"red_alone_signal","stop_boundary","approach_lane","receiving_road"}
    if "pedestrian" in suffix: observed|={"pedestrian_body","pedestrian_yield_response"}
    if "traffic" in suffix: observed|={"traffic_body","traffic_yield_response"}
    (root/"pixel-review.json").write_text(json.dumps({"format":"worker-original-pixel-review",
       "case_id":case_id,"diagnostic_fixture":True,"reviewer":"CPU protocol only",
       "video_sha256":sha(root/"raw.mkv"),"frame_map_sha256":sha(mapping),
       "measurement_sha256":sha(measurement),
       "observations":{name:{"visible":True,"frame":0,"view":"overview",
                             "description":"synthetic protocol placeholder"} for name in observed}}))
    (root/"source-seal.json").write_text(json.dumps({"case_id":case_id,
       "diagnostic_fixture":True,"provenance_kind":"native",
       "source_hashes":{name:sha(root/name) for name in
                        {"site.json","trace.jsonl","frame-map.jsonl","raw.mkv",*CAMERAS}}}))
    return case_id


class DeliveryAuditTests(unittest.TestCase):
    def test_all_eight_diagnostic_protocols_and_default_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            for suffix in KINDS:
                root=base/suffix
                case_id=attempt(root,suffix)
                audit=verify(case_id,root,allow_diagnostic=True)
                self.assertEqual(audit["format"],"c153046-diagnostic-delivery-protocol")
                self.assertFalse(audit["physical_acceptance_claimed"])
                with self.assertRaisesRegex(ValueError,"diagnostic fixture cannot pass"):
                    verify(case_id,root)

    def test_stale_video_pixel_and_frame_join_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"case"
            case_id=attempt(root,"stopped_leftmost_clear")
            (root/"raw.mkv").write_text("changed video\n")
            with self.assertRaisesRegex(ValueError,"sealed original source changed"):
                verify(case_id,root,allow_diagnostic=True)
            case_id=attempt(Path(temp)/"again","stopped_leftmost_clear")
            root=Path(temp)/"again"
            pixels=json.loads((root/"pixel-review.json").read_text())
            pixels["observations"]["red_alone_signal"]["visible"]=False
            (root/"pixel-review.json").write_text(json.dumps(pixels))
            with self.assertRaisesRegex(ValueError,"actual pixels unverified"):
                verify(case_id,root,allow_diagnostic=True)
            root=Path(temp)/"third"
            case_id=attempt(root,"stopped_leftmost_clear")
            mapping=json.loads((root/"frame-map.jsonl").read_text().splitlines()[0])
            mapping["native_frame"]=99
            lines=(root/"frame-map.jsonl").read_text().splitlines()
            lines[0]=json.dumps(mapping)
            (root/"frame-map.jsonl").write_text("\n".join(lines)+"\n")
            seal=json.loads((root/"source-seal.json").read_text())
            seal["source_hashes"]["frame-map.jsonl"]=sha(root/"frame-map.jsonl")
            (root/"source-seal.json").write_text(json.dumps(seal))
            with self.assertRaisesRegex(ValueError,"time join differs"):
                verify(case_id,root,allow_diagnostic=True)


if __name__=="__main__":
    unittest.main()
