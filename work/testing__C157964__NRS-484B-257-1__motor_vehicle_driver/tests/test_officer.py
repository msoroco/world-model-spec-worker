import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


construction=load("officer_construction")
measure=load("officer_measurements")


def body(x):return [[x+dx,y] for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]


class OfficerTests(unittest.TestCase):
    def fixture(self,root,active=True):
        ctx={"native_map_id":"TownX","intersection_id":44,"officer_actor_id":25,
             "authority_source":"reviewed-operator-roster","uniform_video_source":"detail-original",
             "direction_video_source":"front-original","junction_source":"native-polygon",
             "ego_route_source":"native-waypoints",
             "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
        (root/"officer_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,(x,direction) in enumerate(((0,"stop"),(0,"go"),(12,"go"))):
            rows.append({"frame":100+i,"time_s":1+i*.05,"officer_actor_id":25,
                         "officer_direction_observed":direction,
                         "direction_frame_source":"front-original",
                         "traffic_control_observed":active,
                         "ego":{"speed_mps":0 if i<2 else 2,"body_vertices_xy_m":body(x)}})
        cameras=("overview","approach","reference_corner","driver_reference")
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"],
                 "camera_frames":{name:r["frame"] for name in cameras}} for i,r in enumerate(rows)]
        (root/"officer_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
        camera_hashes={}
        for camera in cameras:
            source=root/(camera+".mkv")
            source.write_bytes(("synthetic diagnostic "+camera).encode())
            camera_hashes[camera]=hashlib.sha256(source.read_bytes()).hexdigest()
        review={"officer_history_sha256":hashlib.sha256((root/"officer_history.jsonl").read_bytes()).hexdigest(),
                "video_frames_sha256":hashlib.sha256((root/"video_frames.jsonl").read_bytes()).hexdigest(),
                "camera_sha256":camera_hashes,
                "frames":[{"frame":r["frame"],"video_frame":i,
                           "observed_direction":r["officer_direction_observed"],
                           "officer_visible":True} for i,r in enumerate(rows)]}
        (root/"officer_review.json").write_text(json.dumps(review))

    def test_original_frame_control_at_entry_without_legal_conclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["officer_control_observed_at_entry"])
            self.assertEqual(result["first_ego_entry"]["frame"],102)
            self.assertEqual(result["legal_conclusion"],"unresolved")
            self.fixture(root,False)
            self.assertFalse(measure.analyze(root)["officer_control_observed_at_entry"])

    def test_stale_frame_and_missing_direction_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"review source hash"):measure.analyze(root)
            self.fixture(root)
            rows=[json.loads(r) for r in (root/"officer_history.jsonl").read_text().splitlines()]
            rows[1]["direction_frame_source"]=""
            (root/"officer_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"review source hash"):measure.analyze(root)

    def test_camera_bytes_and_observed_direction_are_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            (root/"approach.mkv").write_bytes(b"changed diagnostic pixels")
            with self.assertRaisesRegex(ValueError,"camera bytes differ"):measure.analyze(root)
            self.fixture(root)
            review=json.loads((root/"officer_review.json").read_text())
            review["frames"][2]["observed_direction"]="stop"
            (root/"officer_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"direction/frame join"):measure.analyze(root)

    def test_real_native_performer_spawn_and_cleanup(self):
        location=NS(x=5.0,y=0.0,z=0.0)
        transform=NS(location=location)
        destroyed=[]
        actor=NS(get_location=lambda:location,destroy=lambda:destroyed.append(True))
        world=NS(try_spawn_actor=lambda blueprint,where:actor)
        with construction.spawn_officer_performer(world,"source-reviewed-blueprint",transform,NS(x=10,y=0,z=0)) as built:
            self.assertEqual(built["surveyed_distance_to_junction_m"],5)
        self.assertEqual(destroyed,[True])
        with self.assertRaisesRegex(ValueError,"placement"):
            with construction.spawn_officer_performer(world,"blueprint",NS(location=NS(x=10,y=0,z=0)),NS(x=10,y=0,z=0)):
                pass


if __name__=="__main__":unittest.main()
