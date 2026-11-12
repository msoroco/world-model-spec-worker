"""Original 20 Hz ego, traffic and contact recorder for intersection backing."""
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


def _body(actor):
    transform=actor.get_transform();location=transform.location
    extent=actor.bounding_box.extent
    values=(location.x,location.y,extent.x,extent.y)
    if any(not isfinite(float(v)) for v in values) or min(extent.x,extent.y)<=0:
        raise ValueError('Native participant body readback is invalid')
    return {'x_m':float(location.x),'y_m':float(location.y),
            'body_radius_m':float(hypot(extent.x,extent.y))}


class BackingSourceRecorder:
    def __init__(self, directory, ego, participants, context):
        self.directory=Path(directory);self.ego=ego
        self.participants={str(actor.id):actor for actor in participants}
        if not self.participants or len(self.participants)!=len(participants) or str(ego.id) in self.participants:
            raise ValueError('Distinct Native traffic participants required')
        if set(self.participants)!=set(context.get('participants',{})):
            raise ValueError('Surrounding traffic context/actor identities differ')
        for actor_id,item in context['participants'].items():
            if item.get('kind') not in ('vehicle','pedestrian') or not item.get('position_motion_purpose_source') or not item.get('highway_use_source'):
                raise ValueError('Every participant needs sourced motion, purpose and highway use')
        self.directory.mkdir(parents=True,exist_ok=True)
        self.context=self.directory/'backing_context.json'
        self.context.write_text(json.dumps(context,indent=2)+'\n')
        self.motion=(self.directory/'backing_motion.jsonl').open('x')
        self.contacts_path=self.directory/'backing_contacts.jsonl'
        self.last=None;self.pending={};self.frames=[]

    def contact(self, frame, other_actor_id):
        actor_id=str(other_actor_id)
        if actor_id not in self.participants or type(frame) is not int:
            raise ValueError('Native contact has unknown actor or invalid frame')
        self.pending.setdefault(frame,set()).add(actor_id)

    def append(self, frame, time_s):
        if type(frame) is not int or type(time_s) not in (int,float) or not isfinite(time_s) or self.last is not None and (frame!=self.last[0]+1 or abs(time_s-self.last[1]-.05)>1e-4):
            raise ValueError('Native backing frame/time sequence differs from 20 Hz')
        heading=self.ego.get_transform().get_forward_vector();velocity=self.ego.get_velocity()
        if any(not isfinite(float(v)) for v in (heading.x,heading.y,velocity.x,velocity.y)):
            raise ValueError('Native backing heading/velocity is nonfinite')
        bodies={}
        for actor_id,actor in self.participants.items():
            body=_body(actor);speed=actor.get_velocity()
            body['speed_mps']=float(hypot(speed.x,speed.y));bodies[actor_id]=body
        row={'frame':frame,'time_s':time_s,'ego':_body(self.ego),
             'ego_heading_xy':[float(heading.x),float(heading.y)],
             'ego_velocity_xy':[float(velocity.x),float(velocity.y)],
             'participants':bodies}
        self.motion.write(json.dumps(row,allow_nan=False)+'\n')
        self.motion.flush();self.last=(frame,time_s);self.frames.append((frame,time_s))
        return row

    def close(self):
        if set(self.pending)-{frame for frame,_ in self.frames}:
            raise ValueError('Unjoined Native contact frame remains')
        self.motion.close()
        with self.contacts_path.open('x') as stream:
            for frame,time_s in self.frames:
                stream.write(json.dumps({'frame':frame,'time_s':time_s,
                    'contact_actor_ids':sorted(self.pending.get(frame,set()))})+'\n')
        return {'backing_motion.jsonl':sha256((self.directory/'backing_motion.jsonl').read_bytes()).hexdigest(),
                'backing_contacts.jsonl':sha256((self.directory/'backing_contacts.jsonl').read_bytes()).hexdigest(),
                'backing_context.json':sha256(self.context.read_bytes()).hexdigest()}
