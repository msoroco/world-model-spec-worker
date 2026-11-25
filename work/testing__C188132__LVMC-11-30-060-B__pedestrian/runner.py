"""Candidate Native C188132 acquisition; no CARLA import during --check."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from native_capture import FourVideoRecorder, sample_original_walker
from media_audit import audit_media
from overpass_source import (FRAMES, native_sample, request_controls, sha,
                             spawn_pair, validate_case)
from site_review import inspect as inspect_site


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def run(scene_path, map_path, output, host, port):
    root = Path(__file__).resolve().parents[2]
    safe = (root/'.runtime-work').resolve()
    output = Path(output).resolve()
    if not output.is_dir() or not output.is_relative_to(safe):
        raise ValueError('fresh attempt directory under .runtime-work required')
    if Path(scene_path).resolve() != output/'scene.json' or Path(map_path).resolve() != output/'candidate-overpass.xodr':
        raise ValueError('exact attempt must contain its source scene and map')
    if any((output/name).exists() for name in ('body-history.jsonl','video_frames.jsonl','capture-seal.json')):
        raise ValueError('original attempt already exists')
    scene = json.loads(Path(scene_path).read_text())
    validate_case(scene, map_path)
    reviewed = os.environ.get('C188132_REVIEWED_SITE_PACKET')
    if not reviewed:
        raise ValueError('C188132_REVIEWED_SITE_PACKET original review required before Native capture')
    reviewed_path = Path(reviewed).resolve()
    inspect_site(reviewed_path, map_path, scene)
    packet = json.loads(reviewed_path.read_text())
    review_sources = {'reviewed-site.json': reviewed_path,
                      'reviewed-site-source.txt': reviewed_path.parent/packet['independent_review']['source'],
                      'municipal-designation-source.txt': reviewed_path.parent/packet['municipal_designation']['source']}
    for name, source in review_sources.items():
        target = output/name
        if target.exists():
            raise ValueError('reviewed source target already exists: '+name)
        shutil.copy2(source, target)
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(safe/'c188132-native-runtime')
    import carla
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore
    from walker_pipeline_capture import WalkerPipelineCapture

    client = carla.Client(host, port)
    client.set_timeout(30)
    previous = snapshot_world(client)
    world = None
    walker = vehicle = videos = capture = frame_map = None
    error = None
    cleanup = []
    restored = {'restored':False}
    count = 0
    try:
        world = client.generate_opendrive_world(Path(map_path).read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        walker, vehicle = spawn_pair(world, carla, scene)
        videos = FourVideoRecorder(world, scene, carla, output)
        capture = WalkerPipelineCapture(client, walker, output, scene['case_id'])
        frame_map = FrameMap(output/'video_frames.jsonl')
        with (output/'body-history.jsonl').open('x', buffering=1) as body, \
             (output/'camera-frame-joins.jsonl').open('x', buffering=1) as joins, \
             (output/'control-requests.jsonl').open('x', buffering=1) as controls:
            for _ in range(FRAMES):
                requested = request_controls(carla, scene, walker, vehicle)
                frame = world.tick()
                snap = world.get_snapshot()
                if frame != snap.frame:
                    raise RuntimeError('world tick and original snapshot differ')
                original = native_sample(scene, snap, walker, vehicle, world)
                walker_body = sample_original_walker(scene, walker, snap)
                if walker_body['frame'] != original['frame']:
                    raise RuntimeError('original body and actor frame differ')
                original['pedestrian_body_xy_m'] = walker_body['body_xy_m']
                original['pedestrian_body_z_m'] = [walker_body['body_z_min_m'], walker_body['body_z_max_m']]
                joined = videos.append(walker_body)
                captured = capture.capture(frame, original['time_s'], walker_body)
                if captured['frame'] != frame:
                    raise RuntimeError('graph and original frame differ')
                frame_map.append(frame, original['time_s'])
                body.write(json.dumps(original, allow_nan=False)+'\n')
                joins.write(json.dumps(joined, allow_nan=False)+'\n')
                controls.write(json.dumps({'frame':frame,'time_s':original['time_s'],
                                           **requested}, allow_nan=False)+'\n')
                count += 1
    except BaseException as exc:
        error = repr(exc)
    finally:
        for resource in (frame_map,capture,videos):
            if resource is not None:
                try:
                    if resource is capture:
                        resource.close(confirmed=error is None)
                    else:
                        resource.close()
                except BaseException as exc:
                    cleanup.append(repr(exc))
        for actor in (vehicle,walker):
            if actor is not None:
                try: actor.destroy()
                except BaseException as exc: cleanup.append(repr(exc))
        try: restored = restore(client, previous)
        except BaseException as exc: cleanup.append('world restoration: '+repr(exc))
    if error or cleanup or not restored.get('restored') or count != FRAMES:
        write(output/'native-run-status.json', {'phase':'failed','errors':[
            value for value in [error,*cleanup] if value], 'captured_frames':count,
            'restoration':restored})
        raise RuntimeError('Native overpass acquisition or restoration failed')
    files = ('scene.json','candidate-overpass.xodr','body-history.jsonl',
             'video_frames.jsonl','camera-frame-joins.jsonl','control-requests.jsonl',
             'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')
    sources = {'scene':'scene.json', 'map':'candidate-overpass.xodr',
               'body_history':'body-history.jsonl', 'frame_map':'video_frames.jsonl',
               'camera_joins':'camera-frame-joins.jsonl',
               'site_review':'reviewed-site.json',
               'site_review_source':'reviewed-site-source.txt',
               'municipal_source':'municipal-designation-source.txt'}
    sources.update({'video_'+name:name+'.mkv' for name in
                    ('overview','approach','reference_corner','driver_reference')})
    write(output/'source-manifest.json', {'format':'c188132-original-sources-v1',
          **{key:{'path':name,'sha256':sha(output/name)} for key,name in sources.items()}})
    write(output/'media-audit.json', audit_media(output))
    write(output/'acquisition.json', {name:{'kind':'original_native','sha256':sha(output/name)}
                                      for name in files})
    seal_capture(output, frames=count, restoration=restored, errors=[],
                 encoder_exit_codes={name:0 for name in
                 ('overview','approach','reference_corner','driver_reference')},
                 context={'case_id':scene['case_id'], 'map_sha256':sha(map_path)})
    return {'case_id':scene['case_id'],'frames':count,
            'native_acquisition_sealed':True,'physical_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scene', default='scene.json')
    parser.add_argument('--map', default='candidate-overpass.xodr')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args=parser.parse_args()
    scene=json.loads(Path(args.scene).read_text())
    validate_case(scene,args.map)
    if args.check:
        print(json.dumps({'case_id':scene['case_id'],'map_sha256':sha(args.map),
                          'planned_frames':FRAMES,'simulation_started':False}))
    elif args.output_dir:
        print(json.dumps(run(args.scene,args.map,args.output_dir,args.host,args.port)))
    else:
        parser.error('use --check or --output-dir')


if __name__ == '__main__':
    main()
