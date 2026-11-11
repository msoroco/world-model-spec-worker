"""Record original Native participant/prop state alongside PipelineCapture.

World, cameras and actor lifetimes belong to the runner. This class retains
only the case-specific sources and original frame map.
"""
import json
from math import hypot
from pathlib import Path


def _point_xy(value):
    return [float(value.x),float(value.y)]


def _actor_state(actor):
    if actor is None or not actor.is_alive:
        raise ValueError('required participant absent from Native world')
    position=actor.get_transform().location
    velocity=actor.get_velocity()
    return _point_xy(position),hypot(velocity.x,velocity.y)


def _prop_geometry(actor):
    if actor is None: return None
    if not actor.is_alive:
        raise ValueError('required physical prop absent from Native world')
    transform=actor.get_transform()
    box=actor.bounding_box
    vertices=box.get_world_vertices(transform)
    if len(vertices)<4:
        raise ValueError('physical prop has no bounding geometry')
    return {'actor_id':int(actor.id),'blueprint_id':actor.type_id,
            'center_xy':_point_xy(transform.location),
            'vertices_xyz':[[float(v.x),float(v.y),float(v.z)] for v in vertices]}


class SlowCaptureSession:
    def __init__(self, output, pipeline_capture, ego, follower, opposing,
                 obstruction, control, context):
        from worker_exchange.native_output import FrameMap
        root=Path(output)
        if context.get('case_branch') not in ('flowing_reference','slow_with_following_traffic',
                                              'slow_for_obstruction','slow_under_control'):
            raise ValueError('exact slow-speed branch required')
        if context['case_branch']=='slow_for_obstruction' and obstruction is None:
            raise ValueError('obstruction branch requires physical prop')
        if context['case_branch']=='slow_under_control' and (control is None or not context.get('regulatory_source')):
            raise ValueError('control branch requires physical device and regulatory source')
        for filename in ('slow_context.json','participant_state.jsonl','prop_state.jsonl','video_frames.jsonl'):
            if (root/filename).exists():
                raise ValueError('Retain prior source; use fresh attempt: '+filename)
        self.pipeline=pipeline_capture
        self.ego,self.follower,self.opposing=ego,follower,opposing
        self.obstruction,self.control=obstruction,control
        (root/'slow_context.json').write_text(json.dumps(context,indent=2)+'\n')
        self.participants=(root/'participant_state.jsonl').open('x')
        self.props=(root/'prop_state.jsonl').open('x')
        self.frames=FrameMap(root/'video_frames.jsonl')
        self.closed=False

    def capture(self, frame, time_s):
        if self.closed: raise ValueError('capture session closed')
        observed={}
        for name,actor in (('ego',self.ego),('follower',self.follower),('opposing',self.opposing)):
            xy,speed=_actor_state(actor)
            observed[name+'_valid']=True
            observed[name+'_xy']=xy
            observed[name+'_speed_mps']=speed
        obstruction=_prop_geometry(self.obstruction)
        control=_prop_geometry(self.control)
        row=self.pipeline.capture(frame,time_s)
        if (row.get('frame'),row.get('time_s'))!=(frame,time_s):
            raise ValueError('PipelineCapture returned another original tick')
        participant={'frame':frame,'time_s':time_s,**observed}
        prop={'frame':frame,'time_s':time_s,
              'obstruction_present':obstruction is not None,
              'obstruction_geometry':obstruction,
              'control_present':control is not None,
              'control_geometry':control,
              # Actual camera visibility is independently audited from pixels.
              'obstruction_visible':None,'control_visible':None}
        self.participants.write(json.dumps(participant)+'\n');self.participants.flush()
        self.props.write(json.dumps(prop)+'\n');self.props.flush()
        self.frames.append(frame,time_s)
        return row

    def close(self):
        if not self.closed:
            self.closed=True
            self.frames.close();self.participants.close();self.props.close()

    def __enter__(self):return self
    def __exit__(self,*_):self.close()
