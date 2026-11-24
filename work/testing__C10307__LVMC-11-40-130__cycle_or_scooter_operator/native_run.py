"""Source-gated, single-run Native bicycle capture adapter.

The operator supplies a SHA-bound local scene and asset inventory. This module
never starts a server; CARLA is imported only by run_native().
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path

from native_acquisition import seal_original_acquisition
from native_controller import run_bicycle_route
from native_spawn import read_asset_inventory, spawn_bicycle_and_rack
from native_capture import FourCameraCapture
from native_geometry import validate_live_route


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound_json(path, expected_sha256):
    path = Path(path)
    if not path.is_file() or sha(path) != expected_sha256:
        raise ValueError("Native source file missing or hash mismatch")
    return json.loads(path.read_text())


def reviewed_packet(reference, name):
    if not isinstance(reference, dict) or not reference.get('path') or not reference.get('sha256'):
        raise ValueError('Native ' + name + ' reviewed source path/hash required')
    packet = bound_json(reference['path'], reference['sha256'])
    if packet.get('source_kind') != 'reviewed_original' or not packet.get('reviewed_by'):
        raise ValueError('Native ' + name + ' source review missing')
    return packet


def pedestrian_source(scene, case_id):
    """Read the reviewed near-rack actor pose used by this exact case."""
    packet = reviewed_packet(scene.get('pedestrian_spawn_source'), 'pedestrian spawn')
    if (packet.get('case_id') != case_id or
            packet.get('blueprint_id') != scene.get('pedestrian_blueprint_id') or
            packet.get('rack_blueprint_id') != scene.get('rack_blueprint_id')):
        raise ValueError('Native pedestrian reviewed packet differs from scene')
    pose = packet.get('spawn_pose')
    if (not isinstance(pose, dict) or set(pose) != {'x', 'y', 'z', 'yaw'} or
            any(type(pose[k]) not in (int, float) or not math.isfinite(pose[k]) for k in pose)):
        raise ValueError('Native pedestrian reviewed spawn pose missing')
    if ((pose['x']) ** 2 + (pose['y'] - 2.3) ** 2) ** .5 > 5.0:
        raise ValueError('Native pedestrian reviewed pose is not near rack')
    return packet


def source_configuration(env, case_id):
    required = ("C10307_SCENE_SOURCE", "C10307_SCENE_SHA256",
                "C10307_ASSET_INVENTORY", "C10307_ASSET_SHA256")
    if any(not env.get(key) for key in required):
        raise ValueError("Native scene and asset inventory paths/hashes required")
    scene = bound_json(env["C10307_SCENE_SOURCE"], env["C10307_SCENE_SHA256"])
    inventory = read_asset_inventory(Path(env["C10307_ASSET_INVENTORY"]), env["C10307_ASSET_SHA256"])
    road_ref = scene.get('road_source')
    if (scene.get("case_id") != case_id or not isinstance(road_ref, dict) or
            not road_ref.get('path') or road_ref.get('sha256') != scene.get('map_sha256') or
            not Path(road_ref['path']).is_file() or sha(road_ref['path']) != road_ref['sha256']):
        raise ValueError("Native scene case/map source mismatch")
    validate_live_route(Path(road_ref['path']))
    if scene.get("human_powered_bicycle_verified") is not True or scene.get("rack_asset_verified") is not True:
        raise ValueError("Native bicycle/rack physical classification source missing")
    jurisdiction = scene.get("jurisdiction", {})
    if jurisdiction.get("city_of_las_vegas") is not True or not jurisdiction.get("source"):
        raise ValueError("Native municipal jurisdiction source missing")
    municipal = reviewed_packet(jurisdiction['source'], 'municipal jurisdiction')
    if (municipal.get('city_of_las_vegas') is not True or
            municipal.get('world_map') != scene.get('world_map') or
            municipal.get('map_sha256') != scene.get('map_sha256')):
        raise ValueError('Native municipal jurisdiction packet differs from scene')
    if inventory.get("world_map") != scene.get("world_map"):
        raise ValueError("Native asset inventory map differs from scene")
    required_blueprints = {scene.get('bicycle_blueprint_id'), scene.get('rack_blueprint_id')}
    if (None in required_blueprints or len(required_blueprints) != 2 or
            not required_blueprints <= set(inventory.get('blueprint_ids', []))):
        raise ValueError('Native bicycle/rack blueprint inventory differs from scene')
    if not scene.get("bicycle_classification_source") or not scene.get("rack_geometry_source"):
        raise ValueError("Native bicycle/rack geometry source missing")
    bicycle = reviewed_packet(scene['bicycle_classification_source'], 'bicycle classification')
    rack = reviewed_packet(scene['rack_geometry_source'], 'rack geometry')
    if (bicycle.get('human_powered') is not True or bicycle.get('moped') is not False or
            bicycle.get('blueprint_id') != scene.get('bicycle_blueprint_id') or
            rack.get('blueprint_id') != scene.get('rack_blueprint_id') or
            rack.get('rack_type') != 'bicycle_rack'):
        raise ValueError('Native bicycle/rack reviewed packets differ from scene')
    if case_id.endswith('__pedestrian_near_rack'):
        pedestrian_source(scene, case_id)
        if scene.get('pedestrian_blueprint_id') not in inventory.get('blueprint_ids', []):
            raise ValueError('Native pedestrian blueprint inventory differs from scene')
    return scene, inventory


def snapshot_sources(output, env, scene, case_id):
    """Keep the exact dispatch sources beside the original recording."""
    output = Path(output).resolve()
    destination = output / 'source-provenance'
    if destination.exists() or (output / 'source-provenance.json').exists():
        raise ValueError('refusing to overwrite Native source provenance')
    references = {
        'scene': {'path': env['C10307_SCENE_SOURCE'], 'sha256': env['C10307_SCENE_SHA256']},
        'asset_inventory': {'path': env['C10307_ASSET_INVENTORY'], 'sha256': env['C10307_ASSET_SHA256']},
        'road': scene['road_source'],
        'municipal': scene['jurisdiction']['source'],
        'bicycle': scene['bicycle_classification_source'],
        'rack': scene['rack_geometry_source'],
    }
    if case_id.endswith('__pedestrian_near_rack'):
        pedestrian_source(scene, case_id)
        references['pedestrian'] = scene['pedestrian_spawn_source']
    captured = {}
    payloads = {}
    for name, reference in references.items():
        source = Path(reference['path'])
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != reference['sha256']:
            raise ValueError('Native source changed before provenance snapshot: ' + name)
        filename = name + ('.xodr' if name == 'road' else '.json')
        payloads[filename] = raw
        captured[name] = {'path': 'source-provenance/' + filename, 'sha256': digest}
    destination.mkdir(parents=True)
    for filename, raw in payloads.items():
        (destination / filename).write_bytes(raw)
    manifest = {'format': 'c10307-native-source-provenance-v1', 'case_id': case_id,
                'world_map': scene['world_map'], 'sources': captured}
    (output / 'source-provenance.json').write_text(json.dumps(manifest, sort_keys=True) + '\n')
    return manifest


def configure_world(world, config):
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = .05
    settings.no_rendering_mode = False
    world.apply_settings(settings)
    actual = world.get_settings()
    if actual.synchronous_mode is not True or actual.no_rendering_mode is not False or abs(actual.fixed_delta_seconds - .05) > 1e-6:
        raise ValueError("Native synchronous RGB settings readback mismatch")
    weather = world.get_weather()
    case = config["case"]["world_setup"]
    weather.fog_density = 2.0
    weather.wetness = 0.0
    weather.precipitation = 0.0
    if case["visibility_condition"] == "reduced":
        weather.fog_density = 70.0
    if case["surface_condition"] == "wet":
        weather.wetness = 75.0
        weather.precipitation = 30.0
    world.set_weather(weather)
    actual_weather = world.get_weather()
    if (case["visibility_condition"] == "reduced" and actual_weather.fog_density < 60) or (case["surface_condition"] == "wet" and actual_weather.wetness < 70):
        raise ValueError("Native weather condition readback mismatch")


def condition(world, rack, row, config):
    weather = world.get_weather()
    walkers = world.get_actors().filter("walker.pedestrian.*")
    rack_location = rack.get_transform().location
    near = []
    for walker in walkers:
        location = walker.get_transform().location
        if ((location.x-rack_location.x)**2 + (location.y-rack_location.y)**2)**.5 <= 5:
            near.append(int(walker.id))
    expected = config["case"]["world_setup"]["pedestrian_condition"] == "pedestrian near rack"
    if expected != bool(near):
        raise ValueError("Native rack pedestrian condition did not realize")
    return {"frame": row["frame_id"], "time_s": row["time_s"],
            "weather": {"cloudiness": weather.cloudiness, "precipitation": weather.precipitation,
                        "fog_density": weather.fog_density, "wetness": weather.wetness},
            "surface": "wet" if weather.wetness >= 70 else "dry",
            "visibility": "reduced" if weather.fog_density >= 60 else "clear",
            "pedestrians": {"within_5m_of_rack_actor_ids": near}, "curvature": "straight authored route"}


def spawn_case_pedestrian(world, carla, scene, inventory, config):
    """Create the declared near-rack pedestrian only in that controlled case."""
    expected = config["case"]["world_setup"]["pedestrian_condition"] == "pedestrian near rack"
    if not expected:
        return None
    source = pedestrian_source(scene, config['selected_case_id'])
    blueprint_id = scene.get("pedestrian_blueprint_id")
    if not blueprint_id or blueprint_id not in inventory.get("blueprint_ids", []):
        raise ValueError("source-gated near-rack pedestrian asset missing")
    blueprint = world.get_blueprint_library().find(blueprint_id)
    if blueprint is None or blueprint.id != blueprint_id:
        raise ValueError("Native near-rack pedestrian blueprint unavailable")
    pose = source['spawn_pose']
    actor = world.spawn_actor(blueprint, carla.Transform(
        carla.Location(x=pose['x'], y=pose['y'], z=pose['z']),
        carla.Rotation(yaw=pose['yaw'])))
    if actor is None or actor.type_id != blueprint_id:
        if actor is not None:
            actor.destroy()
        raise ValueError("Native near-rack pedestrian spawn/readback failed")
    return actor


def run_native(output, host, port, config, env=None):
    env = os.environ if env is None else env
    case_id = config["selected_case_id"]
    scene, inventory = source_configuration(env, case_id)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange import world_restore
    from analysis import finalize, write_native_result
    client = carla.Client(host, int(port))
    client.set_timeout(30.0)
    saved = world_restore.snapshot(client)
    owned = []
    capture = None
    cameras = None
    output = Path(output).resolve()
    try:
        world = client.get_world()
        if world.get_map().name != scene["world_map"] or sha_text(world.get_map().to_opendrive()) != scene["map_sha256"]:
            raise ValueError("Live Native map differs from SHA-bound scene")
        snapshot_sources(output, env, scene, case_id)
        configure_world(world, config)
        bicycle, rack, owned = spawn_bicycle_and_rack(world, carla, scene, inventory)
        pedestrian = spawn_case_pedestrian(world, carla, scene, inventory, config)
        if pedestrian is not None:
            owned.append(pedestrian)
        if not hasattr(bicycle, "get_control"):
            raise ValueError("Native bicycle lacks PipelineCapture vehicle control readback")
        capture = PipelineCapture(client, bicycle, output, case_id,
                                  required_observations=config.get("required_atoms", []))
        cameras = FourCameraCapture(world, carla, config, output)
        conditions = []
        def observe(row):
            capture.capture(row["frame_id"], row["time_s"])
            cameras.capture(row["frame_id"], row["time_s"])
            conditions.append(condition(world, rack, row, config))
        rows = run_bicycle_route(world, carla, bicycle,
                                 target_speed_mps=config["requested_speed_mps"],
                                 max_frames=900, minimum_frames=900, on_tick=observe)
        cameras.close()
        cameras = None
        capture.close()
        capture = None
        if len(rows) != 900 or len(conditions) != 900:
            raise ValueError("Original Native bicycle acquisition is shorter than planned")
        context = {"case_id": case_id, "source_kind": "original_local_native_capture",
                   "jurisdiction": scene["jurisdiction"],
                   "bicycle_classification": {"human_powered": True, "moped": False,
                                              "source": scene["bicycle_classification_source"]},
                   "alley_route": {"source": scene["map_sha256"]},
                   "rack_geometry": {"source": scene["rack_geometry_source"]},
                   "samples": conditions}
        context_source = output / "source-context.json"
        context_source.write_text(json.dumps(context, sort_keys=True, separators=(",", ":")) + "\n")
        sealed = output / "original-bicycle"
        seal_original_acquisition(sealed, case_id, rows, context,
                                  context_source={"path": str(context_source), "sha256": sha(context_source)})
        for name in ("frame-map.json", "bicycle-motion.json", "context.json", "inventory.json"):
            (output / name).write_bytes((sealed / name).read_bytes())
        source_inventory = json.loads((output / "inventory.json").read_text())
        camera_manifest = {"case_id": case_id, "source_kind": "original_live_native",
                           "diagnostic_fixture": False,
                           "frame_map_sha256": source_inventory["sources"]["frame_map"]["sha256"],
                           "cameras": {name: {"path": name + ".mkv",
                                               "sha256": sha(output / (name + ".mkv")),
                                               "frame_ids": [row["frame_id"] for row in rows]}
                                       for name in ("overview", "approach", "reference_corner", "driver_reference")}}
        (output / "camera-manifest.json").write_text(json.dumps(camera_manifest, indent=2) + "\n")
        report = finalize(output)
        (output / "analysis-report.json").write_text(json.dumps(report, indent=2) + "\n")
        write_native_result(output, report)
        return {"case_id": case_id, "original_frames": len(rows), "result": "result.json"}
    finally:
        try:
            if cameras is not None:
                cameras.close(require_frames=False)
        finally:
            try:
                if capture is not None:
                    capture.close(confirmed=False)
            finally:
                try:
                    for actor in reversed(owned):
                        actor.destroy()
                finally:
                    world_restore.restore(client, saved)


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()
