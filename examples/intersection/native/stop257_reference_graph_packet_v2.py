"""Original Native reference packet for line/crosswalk/fallback branches.

Append before graph collection. Geometry files remain immutable original
observations; this packet cannot turn a candidate into a legal nearest point.
"""
import hashlib,json
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def attach(packet,native,output,frame,time_s):
 if packet.get('frame')!=frame or native.get('frame')!=frame or packet.get('time_s')!=time_s or native.get('time_s')!=time_s:raise ValueError('Reference packet requires original same-frame/time Native data')
 if 'stopping_reference_native' in packet:raise ValueError('Original reference field already exists')
 output=Path(output);configuration=json.loads((output/'config.json').read_text());branch=configuration['reference_branch']
 kinds={'stop_sign_marked_line':('marked_stop_line',20,0,'native-line-geometry-before-motion.json'),'no_line_marked_near_side_crosswalk':('marked_near_side_crosswalk',0,80,'native-reference-geometry-before-motion.json'),'no_line_unmarked_sidewalk_connection_crosswalk':('unmarked_sidewalk_connection_crosswalk',0,0,'native-reference-geometry-before-motion.json'),'neither_line_nor_crosswalk_nearest_viewpoint_candidate':('nearest_viewpoint_boundary_candidate',0,0,'native-fallback-geometry-before-motion.json')}
 if branch not in kinds or configuration['observation_branch']['kind']!=branch:raise ValueError('Explicit same actual branch required')
 kind,line_count,zebra_count,name=kinds[branch];source=output/name;geometry=json.loads(source.read_text());reference=native['subject_stopping_reference'];tiles=native['physical_road_marking_tiles'];lines=native['physical_stopline_tiles'];zebra=native['physical_crosswalk_tiles'];inventory=native['governing_native_inventory']
 if geometry['branch']!=branch or reference['kind']!=kind or len(lines)!=line_count or len(zebra)!=zebra_count or len(tiles)!=line_count+zebra_count or inventory['map_sha256']!=geometry['source_map_sha256'] or geometry['source_map_sha256']!=sha(output/'road.xodr'):raise ValueError('Actual geometry/branch/source inventory mismatch')
 west=[v for v in lines if '_west_physical_stopline_' in v['role']]
 if len(west)!=(20 if branch=='stop_sign_marked_line' else 0):raise ValueError('Applicable West line contradicts branch')
 ids={v['actor_id'] for v in tiles};world_ids={v['actor_id'] for v in native['native_actor_inventory']}
 if len(ids)!=len(tiles) or ids!=set(inventory['observed_physical_road_marking_actor_ids']) or not ids<=world_ids or any(len(v['body_vertices_m'])!=8 for v in tiles):raise ValueError('Same-frame actual marking/body identity missing')
 if branch in ['no_line_marked_near_side_crosswalk','no_line_unmarked_sidewalk_connection_crosswalk']:
  if len(geometry['footway_endpoints'])!=2 or geometry['crosswalk_band_native_xy_m']!=[[-8.5,-7],[-7,-7],[-7,7],[-8.5,7]]:raise ValueError('Positive actual lateral footway connections required')
 if branch=='neither_line_nor_crosswalk_nearest_viewpoint_candidate':
  if geometry['Native_marked_registry_points'] or geometry['Native_sidewalk_endpoints_present']:raise ValueError('Fallback no-crosswalk geometry contradicted')
  place=native['driver_place_sight_distance']
  if place!=packet.get('stop257_place_sight') or place['frame']!=frame or place['time_s']!=time_s:raise ValueError('Fallback requires separate actual Native place query graph packet')
 packet['stopping_reference_native']={'schema':'stop257-original-reference-graph-packet-v2','frame':frame,'time_s':time_s,'branch':branch,'source_map_sha256':geometry['source_map_sha256'],'original_before_motion_geometry':{'relative_path':name,'sha256':sha(source),'source_helper_sha256':geometry['source_helper_sha256']},'subject_stopping_reference':reference,'physical_road_marking_tiles':tiles,'physical_stopline_actor_ids':[v['actor_id'] for v in lines],'physical_crosswalk_actor_ids':[v['actor_id'] for v in zebra],'packet_source_sha256':sha(__file__),'nearest_relevant_legal_point_established':False,'semantic_limits':'Original actual geometry/identity/source packet only; place-distance sampling and actual-user visibility remain separate; no authorization, hazard, yielding, intent or lawful progression inference'}
 packet['stop2572_entrance_control_native']={'schema':'stop2572-original-entrance-control-v1','frame':frame,'time_s':time_s,'map_sha256':inventory['map_sha256'],'inventory_helper_sha256':inventory['helper_sha256'],'entrance_obligations':inventory['entrance_obligations'],'participant_entrance_obligations':inventory['participant_entrance_obligations'],'actual_vehicle_waypoints':inventory['actual_vehicle_waypoints'],'traffic_actor_inventory':inventory['traffic_actor_inventory'],'environment_light_inventory':inventory['environment_light_inventory'],'unclassified_actor_types':inventory['unclassified_actor_types'],'scope':'Original Native observations and explicitly authored entrance-obligation context; no legal right-of-way or caution verdict'}
 return packet
