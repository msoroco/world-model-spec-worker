"""Bind a reviewed Native signal asset to an original live traffic-light actor.

The review packet is an external source input, not a declaration made by the
controller. A packet alone cannot establish a phase: every frame also reads the
live actor state. Packets and source images are retained with the attempt.
"""
import hashlib
import json
import math
from pathlib import Path

ARROW=[{'color':'green','shape':'arrow','direction':'straight'}]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite_number(value):
    return type(value) in (int,float) and math.isfinite(value)


def load_binding(packet_path, asset_path):
    """Validate and retain an independently reviewed complete head inventory.

    The packet identifies the exact original asset, actor and installation.
    Its review fields must refer to the original signal geometry, including all
    indications; a generic state label or unbound screenshot is insufficient.
    """
    packet_path=Path(packet_path);asset_path=Path(asset_path)
    packet=json.loads(packet_path.read_text())
    if packet.get('format')!='c111125-reviewed-arrow-asset-v1':
        raise ValueError('unknown arrow asset review format')
    if packet.get('review_method')!='complete-original-head-indication-inventory' or not packet.get('reviewer'):
        raise ValueError('complete independent head inventory review missing')
    if packet.get('asset_sha256')!=digest(asset_path) or not asset_path.read_bytes():
        raise ValueError('arrow asset source hash mismatch or empty asset')
    if packet.get('asset_type') not in ('original_mesh','original_blueprint','original_capture'):
        raise ValueError('arrow asset must be original source')
    if type(packet.get('actor_id')) is not int or packet['actor_id']<0:
        raise ValueError('invalid reviewed signal actor ID')
    if not isinstance(packet.get('blueprint_id'),str) or not packet['blueprint_id'].startswith('traffic.traffic_light'):
        raise ValueError('reviewed blueprint is not a traffic light')
    if packet.get('faces_ego_approach') is not True:
        raise ValueError('reviewed head does not face the ego approach')
    if packet.get('green_indications')!=ARROW:
        raise ValueError('reviewed green head is not sole straight arrow')
    if packet.get('other_illuminated_on_green')!=[]:
        raise ValueError('other indications illuminate on green')
    position=packet.get('position_m');yaw=packet.get('yaw_deg')
    if not isinstance(position,list) or len(position)!=3 or not all(finite_number(v) for v in position):
        raise ValueError('reviewed head position missing')
    if not finite_number(yaw):
        raise ValueError('reviewed head yaw missing')
    if not packet.get('installation_source_ref'):
        raise ValueError('original installation source reference missing')
    return {'packet':packet,'packet_path':packet_path,'asset_path':asset_path,
            'packet_sha256':digest(packet_path),'asset_sha256':digest(asset_path)}


def bind_actor(binding, actor):
    """Require the reviewed installation to match one live Native actor."""
    packet=binding['packet'];transform=actor.get_transform()
    position=[transform.location.x,transform.location.y,transform.location.z]
    yaw=transform.rotation.yaw
    if int(actor.id)!=packet['actor_id'] or str(actor.type_id)!=packet['blueprint_id']:
        raise ValueError('reviewed arrow actor identity mismatch')
    if any(abs(a-b)>.25 for a,b in zip(position,packet['position_m'])):
        raise ValueError('reviewed arrow installation position mismatch')
    if abs(((yaw-packet['yaw_deg']+180)%360)-180)>2:
        raise ValueError('reviewed arrow installation yaw mismatch')
    return actor


def aspect(binding, actor, frame):
    """Read the original per-frame state after actor/source binding."""
    bind_actor(binding,actor)
    green=str(actor.get_state()).split('.')[-1]=='Green'
    return {'source_verified':green,
            'source_ref':'reviewed-asset-sha256:'+binding['asset_sha256']+';packet-sha256:'+binding['packet_sha256'],
            'head_id':int(actor.id),'observed_frame':frame,
            'illuminated_indications':ARROW if green else [],
            'live_state':str(actor.get_state()),
            'packet_sha256':binding['packet_sha256'],
            'asset_sha256':binding['asset_sha256']}
