"""Saved-only source and frame joins for the U-turn finalizer."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis import build_report, SOURCES
from test_uturn_audit import trace


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value)+"\n")


def lines(path, values):
    path.write_text("".join(json.dumps(value)+"\n" for value in values))


class SavedAnalysisTests(unittest.TestCase):
    def build_attempt(self, root):
        sample = trace()
        context = sample["context"]
        (root/"road.xodr").write_text("road")
        context["map_source_sha256"] = sha(root/"road.xodr")
        write(root/"authority-review-source.json",{"establishment":"unresolved"})
        context["authority_review_source_sha256"] = sha(root/"authority-review-source.json")
        props=[{"blueprint_id":"static.prop.barrier","bounds_xy_m":rect,"z_m":0}
               for rect in context["closed_divider_bounds_xy_m"]]
        write(root/"reviewed-median-context.json",{"context":context,"divider_props":props})
        write(root/"divider-geometry.json",{"actors":[
            {"actor_id":ident,"blueprint_id":"static.prop.barrier",
             "body_vertices_xy_m":[[rect[0],rect[1]],[rect[2],rect[1]],
                                    [rect[2],rect[3]],[rect[0],rect[3]]]}
            for ident,rect in zip((31,32),context["closed_divider_bounds_xy_m"])]})
        context = {**context,"ego_actor_id":7,"divider_actor_ids":[31,32],
                   "reviewed_context_sha256":sha(root/"reviewed-median-context.json")}
        write(root/"median-context.json",context)
        rows = [{**r,"actor_id":7} for r in sample["samples"]]
        lines(root/"ego-body-history.jsonl",rows)
        lines(root/"controller-history.jsonl",[{"frame":r["frame"],
            "time_s":r["time_s"],"ego_actor_id":7,"next_tick_request":{}} for r in rows])
        lines(root/"video_frames.jsonl",[{"carla_frame":r["frame"],
            "video_frame":i,"time_s":r["time_s"]} for i,r in enumerate(rows)])
        lines(root/"trace.jsonl",[{"frame":r["frame"]} for r in rows])
        write(root/"acquisition-provenance.json",{"provenance_kind":"native",
            "diagnostic_fixture":False,
            "reviewed_context_sha256":sha(root/"reviewed-median-context.json")})
        write(root/"acquisition.json",{name:{"kind":"original_native","sha256":sha(root/name)}
                                        for name in SOURCES})

    def test_original_measurement_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.build_attempt(root)
            report = build_report(root)
            value = report["measurements"]["median_uturn_measurement"]["value"]
            self.assertTrue(value["engineering_crossing_observed"])
            self.assertEqual(value["legal_judgment"],"unresolved")
            mapping = root/"video_frames.jsonl"
            records = [json.loads(line) for line in mapping.read_text().splitlines()]
            records[2]["carla_frame"] = 90
            lines(mapping,records)
            with self.assertRaisesRegex(ValueError,"stale original Native source"):
                build_report(root)
            acquisition = json.loads((root/"acquisition.json").read_text())
            acquisition["video_frames.jsonl"]["sha256"] = sha(mapping)
            write(root/"acquisition.json",acquisition)
            with self.assertRaisesRegex(ValueError,"identity join"):
                build_report(root)


if __name__ == "__main__":
    unittest.main()
