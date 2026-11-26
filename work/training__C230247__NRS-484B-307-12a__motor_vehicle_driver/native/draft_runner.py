"""Exact unselected lane-control fixture. Native acquisition still requires review."""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ASSIGNMENT = 'training__C230247__NRS-484B-307-12a__motor_vehicle_driver'
CAMERAS = ('overview','approach','overhead_signal','driver_reference')
HERE = Path(__file__).resolve().parent


def request(frame, case_id):
    if type(frame) is not int or not 0 <= frame < 600:
        raise ValueError('frame outside 600-frame contract')
    if case_id not in (ASSIGNMENT+'__probe_same_lane',ASSIGNMENT+'__probe_other_lane'):
        raise ValueError('unknown exact case')
    lane = -2 if case_id.endswith('other_lane') else -1
    return {'frame':frame,'target_lane_id':lane,'target_speed_mps':4.0,
            'signal_id':100,'governing_signal_lane_id':-1,
            'signal_indication_request':'green_down_arrow'}


def source_row(index, native_frame, elapsed_s, actor, signal_state, signal_inventory, waypoint, proposed_lane_id):
    if type(index) is not int or not 0 <= index < 600 or type(native_frame) is not int:
        raise ValueError('original frame identity required')
    if actor is None or signal_state is None or signal_inventory is None or waypoint is None:
        raise ValueError('post-tick Native source packets required')
    if signal_inventory.get('authority_source') != 'map_signal_inventory' or not signal_inventory.get('authority_verified'):
        raise ValueError('official signal inventory and verification required')
    if signal_inventory.get('mount_source') != 'map_signal_transform':
        raise ValueError('signal mount must come from the Native map')
    if signal_state.get('source') != 'native_signal_state' or signal_state.get('signal_id') != signal_inventory.get('id'):
        raise ValueError('original indication state does not join the governed signal')
    if proposed_lane_id not in (-1,-2):
        raise ValueError('proposed lane absent')
    pose=actor.get_transform()
    vertices=actor.bounding_box.get_world_vertices(pose)
    if len(vertices)!=8:
        raise ValueError('actor body vertices missing')
    return {'frame':index,'native_frame':native_frame,'time_s':elapsed_s,
            'source':'native_post_tick',
            'vehicle':{'source':'native_actor_pose','lane_source':'map_waypoint_projection',
                       'actor_id':actor.id,'actor_blueprint':actor.type_id,
                       'yaw_deg':pose.rotation.yaw,'body_vertices_m':[[v.x,v.y,v.z] for v in vertices],
                       'lane_id':waypoint.lane_id,'proposed_lane_id':proposed_lane_id},
            'signal':{'id':signal_inventory['id'],'source':'native_signal_state',
                      'authority_source':'map_signal_inventory','authority_verified':True,
                      'mount_source':'map_signal_transform','mount_m':signal_inventory['mount_m'],
                      'lane_id':signal_inventory['lane_id'],'mount_lane_id':signal_inventory['mount_lane_id'],
                      'indication':signal_state['indication'],
                      'facing_yaw_deg':signal_inventory['facing_yaw_deg']}}


def check(config):
    if (config.get('law_id'),config.get('cell_id'),config.get('actor')) != ('NRS-484B-307-12a','C230247','motor_vehicle_driver'):
        raise ValueError('frozen identity differs')
    cid=config.get('case_id')
    if cid not in (ASSIGNMENT+'__probe_same_lane',ASSIGNMENT+'__probe_other_lane'):
        raise ValueError('case identity differs')
    if config.get('rate_hz')!=20 or config.get('duration_s')!=30:
        raise ValueError('30-second timing differs')
    if tuple(c['name'] for c in config.get('cameras',[]))!=CAMERAS:
        raise ValueError('four-camera profile differs')
    root=ET.parse(HERE/'road.xodr').getroot()
    lanes=[root.find(f".//lane[@id='{i}']") for i in (-1,-2)]
    if any(l is None or l.get('type')!='driving' or float(l.find('width').get('a'))!=3.5 for l in lanes):
        raise ValueError('two driving lanes absent')
    signal=root.find(".//signal[@id='100']")
    if signal is None or signal.get('dynamic')!='yes' or signal.find('validity').attrib != {'fromLane':'-1','toLane':'-1'}:
        raise ValueError('governing overhead signal absent')
    if float(signal.get('zOffset'))<4.0:
        raise ValueError('overhead mount absent')
    req=request(300,cid)
    if req['target_lane_id']!=(-2 if cid.endswith('other_lane') else -1):
        raise ValueError('controlled comparison differs')
    return {'passed':True,'case_id':cid,'frames':600,'rate_hz':20,'cameras':list(CAMERAS),
            'signal_id':100,'signal_valid_lane_id':-1,'target_lane_id':req['target_lane_id'],
            'native_capture_implemented':False,'physical_observation_claimed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if not args.check:
        raise SystemExit('Native CARLA orchestration remains unfinished')
    print(json.dumps(check(json.loads((HERE/'config.json').read_text())),sort_keys=True))
