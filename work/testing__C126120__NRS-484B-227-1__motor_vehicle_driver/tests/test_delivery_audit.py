import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis import build_report
from delivery_audit import audit, sha
import test_analysis as fixtures


class DeliveryAuditTests(unittest.TestCase):
    def test_wrong_roadway_audit_requires_original_body_occupancy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            observed={"non_right_roadway_final_occupancy":True,
                "opening_full_body_frames":[2],
                "roadway_centerline_crossings":[{"through_opening":True}],
                "closed_divider_contact_frames":[],
                "destination_right_roadway_departure_observed":False}
            case_id="testing__C126120__NRS-484B-227-1__motor_vehicle_driver__wrong_roadway"
            fixtures.write(root/"config.json",{"selected_case_id":case_id,
                "case":{"physical_target":"non_right_roadway"}})
            fixtures.write(root/"result.json",{"case_id":case_id,"measured_values":observed,
                "target_checks":[
                    {"target":"non-right roadway reached through opening",
                     "measured":True,"matched":True},
                    {"target":"destination right roadway not reached",
                     "measured":False,"matched":True}],
                "setup_confirmed":True,"behavior_attempted":True,"maneuver_completed":True})
            fixtures.write(root/"acquisition-provenance.json",
                {"provenance_kind":"native","diagnostic_fixture":False})
            for name in ("overview","approach","reference_corner","driver_reference"):
                (root/(name+".mkv")).write_bytes(b"fixture video")
            fixtures.write(root/"capture-seal.json",{"format":"worker-sealed-capture",
                "provenance_kind":"native","diagnostic_fixture":False,
                "restoration":{"restored":True},
                "sources":{p.name:sha(p) for p in root.iterdir() if p.is_file()}})
            report={"measurements":{"median_uturn_measurement":{"value":observed}}}
            with patch("delivery_audit.build_report",return_value=report), \
                 patch("delivery_audit.SOURCES",()):
                self.assertTrue(audit(root)["delivery_physical_audit_passed"])
                observed["non_right_roadway_final_occupancy"]=False
                result=json.loads((root/"result.json").read_text())
                result["measured_values"]=observed
                fixtures.write(root/"result.json",result)
                with self.assertRaisesRegex(ValueError,"physical target lacks matching"):
                    audit(root)
                stayed={"source_right_roadway_all_frames":True,
                        "source_right_roadway_final_occupancy":True,
                        "opening_contact_frames":[],"closed_divider_contact_frames":[],
                        "u_turn_orientation_observed":False,
                        "destination_right_roadway_departure_observed":False}
                no_turn_id="testing__C126120__NRS-484B-227-1__motor_vehicle_driver__right_roadway_no_turn"
                fixtures.write(root/"config.json",{"selected_case_id":no_turn_id,
                    "case":{"physical_target":"source_right_roadway_continuation"}})
                fixtures.write(root/"result.json",{"case_id":no_turn_id,
                    "measured_values":stayed,"target_checks":[
                        {"target":"source right roadway continued without turn",
                         "measured":True,"matched":True}],
                    "setup_confirmed":True,"behavior_attempted":True,
                    "maneuver_completed":True})
                report["measurements"]["median_uturn_measurement"]["value"]=stayed
                self.assertTrue(audit(root)["delivery_physical_audit_passed"])
                stayed["opening_contact_frames"]=[3]
                result=json.loads((root/"result.json").read_text())
                result["measured_values"]=stayed
                fixtures.write(root/"result.json",result)
                with self.assertRaisesRegex(ValueError,"physical target lacks matching"):
                    audit(root)

    def test_closed_divider_approach_audit_and_false_success_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            fixtures.SavedAnalysisTests().build_attempt(root)
            body=[]
            for frame,y in enumerate((-2,-1.8,-1.5,-1.25)):
                body.append({"frame":frame,"time_s":frame/20,"actor_id":7,
                             "body_vertices_xy_m":[[1.8,y-.2],[2.2,y-.2],
                                                   [2.2,y+.2],[1.8,y+.2]],
                             "heading_deg":90,"velocity_xy_mps":[0,1]})
            fixtures.lines(root/"ego-body-history.jsonl",body)
            fixtures.lines(root/"controller-history.jsonl",[
                {"frame":r["frame"],"time_s":r["time_s"],"ego_actor_id":7,
                 "next_tick_request":{}} for r in body])
            fixtures.lines(root/"video_frames.jsonl",[
                {"carla_frame":r["frame"],"video_frame":i,"time_s":r["time_s"]}
                for i,r in enumerate(body)])
            fixtures.lines(root/"trace.jsonl",[{"frame":r["frame"]} for r in body])
            acquisition=json.loads((root/"acquisition.json").read_text())
            for name in ("ego-body-history.jsonl","controller-history.jsonl",
                         "video_frames.jsonl","trace.jsonl"):
                acquisition[name]["sha256"]=sha(root/name)
            for item in acquisition.values():item["kind"]="original_native"
            fixtures.write(root/"acquisition.json",acquisition)
            provenance=json.loads((root/"acquisition-provenance.json").read_text())
            provenance.update(provenance_kind="native",diagnostic_fixture=False)
            fixtures.write(root/"acquisition-provenance.json",provenance)
            observed=build_report(root)["measurements"]["median_uturn_measurement"]["value"]
            self.assertFalse(observed["engineering_crossing_observed"])
            self.assertTrue(0 < observed["final_closed_divider_clearance_m"] <= 1)
            case_id="testing__C126120__NRS-484B-227-1__motor_vehicle_driver__closed_divider"
            fixtures.write(root/"config.json",{"selected_case_id":case_id,
                "case":{"physical_target":"closed_divider_approach"}})
            fixtures.write(root/"result.json",{"case_id":case_id,"measured_values":observed,
                "target_checks":[
                    {"target":"closed-divider approach with full-body clearance",
                     "measured":True,"matched":True},
                    {"target":"destination right roadway not reached",
                     "measured":False,"matched":True}],
                "setup_confirmed":True,"behavior_attempted":True,"maneuver_completed":True})
            for name in ("overview","approach","reference_corner","driver_reference"):
                (root/(name+".mkv")).write_bytes(b"fixture video")
            fixtures.write(root/"capture-seal.json",{"format":"worker-sealed-capture",
                "provenance_kind":"native","diagnostic_fixture":False,
                "restoration":{"restored":True},
                "sources":{p.name:sha(p) for p in root.iterdir() if p.is_file()}})
            self.assertTrue(audit(root)["delivery_physical_audit_passed"])
            result=json.loads((root/"result.json").read_text())
            result["target_checks"][0]["measured"]=False
            fixtures.write(root/"result.json",result)
            with self.assertRaisesRegex(ValueError,"physical target lacks matching"):
                audit(root)

    def test_diagnostic_fixture_cannot_pass_native_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            fixtures.SavedAnalysisTests().build_attempt(root)
            observed=build_report(root)["measurements"]["median_uturn_measurement"]["value"]
            fixtures.write(root/"result.json",{"measured_values":observed,"target_checks":[],
                "setup_confirmed":True,"behavior_attempted":True,"maneuver_completed":True})
            for name in ("overview","approach","reference_corner","driver_reference"):
                (root/(name+".mkv")).write_bytes(b"diagnostic video")
            fixtures.write(root/"capture-seal.json",{"format":"worker-sealed-capture",
                "provenance_kind":"native","diagnostic_fixture":False,
                "restoration":{"restored":True},
                "sources":{p.name:sha(p) for p in root.iterdir() if p.is_file()}})
            with self.assertRaisesRegex(ValueError,"Native sealed capture"):
                audit(root)

    def test_rejects_unsealed_and_changed_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures.SavedAnalysisTests().build_attempt(root)
            provenance=json.loads((root/"acquisition-provenance.json").read_text())
            provenance.update(provenance_kind="native",diagnostic_fixture=False)
            fixtures.write(root/"acquisition-provenance.json",provenance)
            acquisition=json.loads((root/"acquisition.json").read_text())
            for source in acquisition.values(): source["kind"]="original_native"
            fixtures.write(root/"acquisition.json",acquisition)
            measured = build_report(root)["measurements"]["median_uturn_measurement"]["value"]
            case_id="testing__C126120__NRS-484B-227-1__motor_vehicle_driver__opening_single"
            fixtures.write(root/"config.json",{"selected_case_id":case_id,
                "case":{"physical_target":"opening_uturn"}})
            fixtures.write(root/"result.json",{"case_id":case_id,"measured_values":measured,
                "target_checks":[{"target":"realized multiple-movement U-turn",
                                  "measured":False,"matched":True},
                                 {"target":"full-body opening crossing without closed-divider contact",
                                  "measured":True,"matched":True}],
                "setup_confirmed":True,"behavior_attempted":True,"maneuver_completed":True})
            for name in ("overview","approach","reference_corner","driver_reference"):
                (root/(name+".mkv")).write_bytes(b"video")
            with self.assertRaisesRegex(FileNotFoundError,"capture-seal"):
                audit(root)
            sources={p.name:sha(p) for p in root.iterdir() if p.is_file()}
            fixtures.write(root/"capture-seal.json",{"format":"worker-sealed-capture",
                "provenance_kind":"native","diagnostic_fixture":False,
                "restoration":{"restored":True},"sources":sources})
            self.assertTrue(audit(root)["delivery_physical_audit_passed"])
            (root/"overview.mkv").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError,"sealed original source changed"):
                audit(root)


if __name__ == "__main__":
    unittest.main()
