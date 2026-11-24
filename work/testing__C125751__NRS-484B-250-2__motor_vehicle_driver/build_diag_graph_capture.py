"""Prototype a synthetic Core graph handoff from original-shaped timing data.

This is software-only diagnostic material. It is never a Native acquisition
receipt, physical outcome, or substitute for the original PipelineCapture.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import shutil
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(',', ':'))+'\n')


def build(source, seed, destination):
    source, seed, destination = map(lambda p: Path(p).resolve(),
                                    (source, seed, destination))
    if '.runtime-work' not in destination.parts or destination.exists():
        raise ValueError('fresh diagnostic destination under .runtime-work required')
    shutil.copytree(source, destination, copy_function=shutil.copy2)
    original = [json.loads(line) for line in (source/'trace.jsonl').read_text().splitlines()]
    sample_event = json.loads((seed/'capture/evidence.jsonl').read_text().splitlines()[0])
    sample_graph = json.loads(next((seed/'capture/native/graphs/base').glob('*.adapter.json')).read_text())
    sample_index = json.loads((seed/'capture/native/frames.jsonl').read_text().splitlines()[0])
    trace, events, indices = [], [], []
    graphs = destination/'capture/native/graphs/base'
    graphs.mkdir(parents=True)
    for source_row in original:
        frame, time_s = source_row['frame'], source_row['time_s']
        position = source_row['position']
        xyz = [position[k] for k in ('x','y','z')]
        speed = source_row['speed_mps']
        telemetry = {'frame':frame,'time_s':time_s,'position':position,
                     'position_m':xyz,'heading_deg':source_row['heading_deg'],
                     'speed_mps':speed,'speed_mph':speed/.44704,
                     'velocity_mps':[speed,0,0],
                     'control':{'throttle':0,'steer':0,'brake':0,'hand_brake':False,
                                'reverse':False,'manual_gear_shift':False,'gear':0}}
        trace.append(telemetry)
        event = copy.deepcopy(sample_event)
        event.update(original_frame=frame,replay_frame=frame,actor_id=10,
                     recording_time_s=time_s,replay_simulation_time_s=time_s)
        event['ego'].update(position_m=xyz,heading_deg=source_row['heading_deg'],
                            speed_mps=speed,speed_provenance='synthetic_native_sample',
                            body_vertices_m=[[x,y,0] for x,y in source_row['body_vertices_m']])
        event['world']['road_projection']['road_id']=source_row['road_id']
        observed = event['original_observations']
        observed.update(frame=frame,time_s=time_s)
        observed['rgb_sensors']=[{key:sensor[key] for key in
                                  ('actor_id','blueprint','parent_actor_id')}
                                 for sensor in observed['rgb_sensors']]
        for participant in observed.get('participants',[]):
            if participant.get('actor_id')==sample_event['actor_id']:
                participant.update(actor_id=10,position_m=xyz,
                                   heading_deg=source_row['heading_deg'],
                                   velocity_mps=[speed,0,0],speed_mps=speed,
                                   body_vertices_m=event['ego']['body_vertices_m'])
                for optional in ('blueprint_attributes','light_attributes',
                                 'wheel_angle_reference'):
                    participant.pop(optional,None)
        events.append(event)
        relative=f'graphs/base/{frame:08d}.adapter.json'
        graph=copy.deepcopy(sample_graph)
        graph['metadata'].update(frame=frame,simulation_time_s=time_s,
                                 observed_evidence=observed)
        for node in graph['nodes']:
            if node['id']=='ego':
                heading=math.radians(source_row['heading_deg'])
                node['attributes'].update(vertex=xyz,entity_id=10,
                                          threedbbox=event['ego']['body_vertices_m'],
                                          forward=[math.cos(heading),math.sin(heading),0],
                                          carla_speed=speed)
        (destination/'capture/native'/relative).write_text(json.dumps(graph,separators=(',',':'))+'\n')
        index=copy.deepcopy(sample_index)
        index.update(frame=frame,simulation_time=time_s,adapter_graph=relative)
        indices.append(index)
    (destination/'trace.jsonl').unlink()
    write_rows(destination/'trace.jsonl',trace)
    write_rows(destination/'capture/evidence.jsonl',events)
    write_rows(destination/'capture/native/frames.jsonl',indices)
    shutil.copy2(seed/'road.xodr',destination/'road.xodr')
    shutil.copy2(seed/'capture/native_map_facts.json',destination/'capture/native_map_facts.json')
    (destination/'carla_recorder.log').write_text('synthetic diagnostic recorder placeholder\n')
    recorder_info=(seed/'capture/recorder_info.txt').read_text()
    recorder_info=recorder_info.replace('Create 205:', 'Create 10:')
    (destination/'capture/recorder_info.txt').write_text(recorder_info)
    manifest=json.loads((seed/'capture/manifest.json').read_text())
    manifest.update(case_id=json.loads((destination/'config.json').read_text())['selected_case_id'],
                    frames=len(original),source_run=str(destination),
                    acquisition='synthetic_fixture',extraction_confirmed=True)
    manifest['sources']={name:digest(destination/name) for name in
                         ('road.xodr','trace.jsonl','carla_recorder.log')}
    (destination/'capture/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return {'frames':len(original),'capture_evidence_sha256':digest(destination/'capture/evidence.jsonl'),
            'physical_acceptance_claimed':False,'synthetic_fixture':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True)
    parser.add_argument('--seed',required=True)
    parser.add_argument('--destination',required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.source,args.seed,args.destination),indent=2))
