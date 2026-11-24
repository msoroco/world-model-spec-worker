"""Propagate the canonical source recording plan into exact constructions."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def refresh(manifest_name, canonical):
    path = HERE / manifest_name
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        refs = [entry] + entry["candidates"]
        for ref in refs:
            construction_path = HERE / ref["construction"]
            construction = json.loads(construction_path.read_text())
            config_file = next(f for f in construction["files"] if f["path"] == "config.json")
            config = json.loads(config_file["content"])
            construction["recording_description"] = canonical
            config["recording_description"] = canonical
            config_file["content"] = json.dumps(config, indent=2) + "\n"
            finalizer_file = next(f for f in construction["files"] if f["path"] == "finalize.py")
            finalizer = finalizer_file["content"]
            if "'source_camera_views': {'video_frame':" not in finalizer:
                before = "    destination = attempt / 'channels'\n"
                after = ("    camera_sources = {name: {'reference': name + '.mkv', 'sha256': sha(attempt / (name + '.mkv'))}\n"
                         "                      for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}\n"
                         "    destination = attempt / 'channels'\n")
                assert finalizer.count(before) == 1
                finalizer = finalizer.replace(before, after)
                before = "        'kin.heading', 'kin.velocity', 'native_body_pose_control', 'camera_frame_join')}"
                after = "        'kin.heading', 'kin.velocity', 'native_body_pose_control', 'camera_frame_join',\n        'source_camera_views')}"
                assert finalizer.count(before) == 1
                finalizer = finalizer.replace(before, after)
                before = "            'camera_frame_join': frame_map,\n"
                after = ("            'camera_frame_join': frame_map,\n"
                         "            'source_camera_views': {'video_frame': frame_map['video_frame'],\n"
                         "                                    'native_frame': sample['native_frame'],\n"
                         "                                    'sources': camera_sources},\n")
                assert finalizer.count(before) == 1
                finalizer = finalizer.replace(before, after)
                finalizer_file["content"] = finalizer
            runner_file = next(f for f in construction["files"] if f["path"] == "runner.py")
            runner = runner_file["content"]
            if "'intersection_geometry':" not in runner:
                before = "        write_new(output/\"context.json\",{'surveyed_intersection':survey})"
                after = ("        write_new(output/\"context.json\",{\n"
                         "            'surveyed_intersection':survey,\n"
                         "            'intersection_geometry':{'native_map_sha256':native_hash,\n"
                         "                'intersection_polygon_xy_m':survey['intersection_polygon_xy_m'],\n"
                         "                'source':'Native OpenDRIVE junction and lane readback'},\n"
                         "            'crosswalk_geometry':{'native_map_sha256':native_hash,\n"
                         "                'near_route_crosswalks_xy_m':[],\n"
                         "                'source':'Native get_crosswalks readback of selected area'},\n"
                         "            'corner_geometry':{'native_map_sha256':native_hash,\n"
                         "                'junction_polygon_xy_m':survey['intersection_polygon_xy_m'],\n"
                         "                'source':'Native junction readback; physical corner path review pending'}})")
                assert runner.count(before) == 1
                runner_file["content"] = runner.replace(before, after)
            write(construction_path, construction)
            ref["construction_sha256"] = sha(construction_path)
        if manifest_name == "execution-manifest.json":
            # Proof fields are deliberately cleared until their new hashes are bound.
            for ref in refs:
                ref.pop("offline", None)
                ref.pop("compatibility", None)
                ref.pop("saved_cpu_proof", None)
    write(path, manifest)
    return sha(path)


def main():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    canonical = proposal["cases"][0]["recording_description"]
    assert all(case["recording_description"] == canonical for case in proposal["cases"])
    for generator_name in ("current-600-primary-generator.json", "current-600-controlled-generator.json"):
        generator_path = HERE / generator_name
        generator = json.loads(generator_path.read_text())
        trace = [json.loads(line) for line in generator["files"]["trace.jsonl"].splitlines()]
        motion = [json.loads(line) for line in generator["files"]["native_samples.jsonl"].splitlines()]
        assert len(trace) == len(motion) == 600
        for row, sample in zip(trace, motion):
            assert row["frame"] == sample["native_frame"]
            signed = sample["signed_forward_velocity_m_s"]
            forward = sample["native_forward_xy"]
            row["velocity_mps"] = [signed * forward[0], signed * forward[1], 0.0]
        generator["files"]["trace.jsonl"] = "\n".join(json.dumps(row) for row in trace) + "\n"
        capture_manifest = json.loads(generator["files"]["capture/manifest.json"])
        capture_manifest["sources"]["trace.jsonl"] = hashlib.sha256(
            generator["files"]["trace.jsonl"].encode()).hexdigest()
        generator["files"]["capture/manifest.json"] = json.dumps(capture_manifest)
        context = json.loads(generator["files"]["context.json"])
        survey = context["surveyed_intersection"]
        context.update({
            "intersection_geometry": {"native_map_sha256": survey["native_map_sha256"],
                "intersection_polygon_xy_m": survey["intersection_polygon_xy_m"],
                "source": "synthetic authored junction fixture; original Native review pending"},
            "crosswalk_geometry": {"native_map_sha256": survey["native_map_sha256"],
                "near_route_crosswalks_xy_m": [],
                "source": "synthetic authored junction fixture; original Native review pending"},
            "corner_geometry": {"native_map_sha256": survey["native_map_sha256"],
                "junction_polygon_xy_m": survey["intersection_polygon_xy_m"],
                "source": "synthetic authored junction fixture; original Native review pending"},
        })
        generator["files"]["context.json"] = json.dumps(context)
        write(generator_path, generator)
        recipe_name = "current-600-primary-recipe.json" if "primary" in generator_name else "current-600-controlled-recipe.json"
        recipe_path = HERE / recipe_name
        recipe = json.loads(recipe_path.read_text())
        recipe["generator"]["sha256"] = sha(generator_path)
        write(recipe_path, recipe)
    for name in ("draft-execution-manifest.json", "current-compat-matrix-manifest.json", "execution-manifest.json"):
        print(name, refresh(name, canonical))
    # The selected root config is the first primary bundle's config.
    selected = json.loads((HERE / "execution-manifest.json").read_text())["cases"][0]
    construction = json.loads((HERE / selected["construction"]).read_text())
    config = next(f["content"] for f in construction["files"] if f["path"] == "config.json")
    (HERE / "config.json").write_text(config)


if __name__ == "__main__":
    main()
