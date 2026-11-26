"""Run 30-second source-shaped diagnostic and negative probes on the meter."""
import copy
import json
import os
import tempfile
from pathlib import Path
from lane_arrow_meter import measure, measure_file
from draft_runner import source_row
from signal_source import map_inventory, observed_state
from capture import check as capture_check


def packet(signal_lane=-1, proposed_lane=-1, indication='green_down_arrow', yaw=0.0,
           occupied_lane=-1):
    return {'format':'synthetic-source-shaped-diagnostic', 'frames':[
        {'frame':i,'native_frame':5000+i,'time_s':round(i/20,3),'source':'native_post_tick',
         'signal':{'id':100,'source':'native_signal_state','authority_source':'map_signal_inventory',
                   'inventory_verified':True,'official_authority_review_pending':True,
                   'mount_m':[30.0,-1.75,4.5],
                   'mount_source':'map_signal_transform','lane_id':signal_lane,
                   'mount_lane_id':signal_lane,'facing_yaw_deg':0.0,'indication':indication},
         'vehicle':{'source':'native_actor_pose','lane_source':'map_waypoint_projection',
                    'lane_id':occupied_lane,'proposed_lane_id':proposed_lane,'yaw_deg':yaw,
                    'body_vertices_m':[[float(j),-1.75 if occupied_lane==-1 else -5.25,0.0] for j in range(8)]}}
        for i in range(600)]}


def main():
    opendrive=Path(__file__).with_name('road.xodr').read_text()
    inventory_readback=map_inventory(opendrive)
    assert inventory_readback['lane_id']==-1 and inventory_readback['mount_m']==[60.0,-1.75,4.5]
    assert inventory_readback['official_authority_review_pending'] is True
    capture_plan={'rate_hz':20,'duration_s':30,'cameras':[
        {'name':name} for name in ('overview','approach','reference_corner','driver_reference')]}
    assert capture_check(capture_plan,opendrive)['authored_end_x_m']==85.0
    broken_plan=copy.deepcopy(capture_plan)
    broken_plan['cameras'].pop()
    try:
        capture_check(broken_plan,opendrive)
    except ValueError:
        pass
    else:
        raise AssertionError('accepted missing fourth camera')
    class Arrow:
        id=19
        type_id='traffic.lane_control_signal'
        attributes={'opendrive_signal_id':'100','display_role':'downward_green_arrow'}
        def get_state(self): return 'green_down_arrow'
    assert observed_state(Arrow(),inventory_readback)['indication']=='green_down_arrow'
    class Generic(Arrow):
        type_id='traffic.traffic_light'
    try:
        observed_state(Generic(),inventory_readback)
    except ValueError:
        pass
    else:
        raise AssertionError('accepted generic traffic light as a downward arrow')
    class GenericGreen(Arrow):
        def get_state(self): return 'Green'
    try:
        observed_state(GenericGreen(),inventory_readback)
    except ValueError:
        pass
    else:
        raise AssertionError('accepted generic Green state as a downward arrow')
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temp:
        source = Path(temp)/'source.json'
        source.write_text(json.dumps(packet(),separators=(',',':'))+'\n')
        baseline = measure_file(source)
        assert baseline['frames'] == 600 and baseline['facing_green_proposed_frames'] == 600
        assert baseline['facing_green_occupied_frames'] == 600
        mismatch = measure(packet(proposed_lane=-2,occupied_lane=-2))
        assert mismatch['facing_green_proposed_frames'] == 0 and mismatch['facing_green_occupied_frames'] == 0
        reversed_driver = measure(packet(yaw=180))
        assert reversed_driver['facing_green_proposed_frames'] == 0
        red = measure(packet(indication='red_x'))
        assert red['red_x_frames'] == 600 and red['facing_green_proposed_frames'] == 0
        shifted=packet()
        for row in shifted['frames']:
            row['native_frame'] += 37
            row['time_s'] += 1.25
        assert measure(shifted)['facing_green_proposed_frames']==600
        probes = ['source','authority_source','inventory_verified','official_authority_review_pending','mount_source','mount_m','mount_lane_id','lane_id','yaw_deg','proposed_lane_id','body_vertices_m','native_frame','time_s']
        for key in probes:
            bad = packet()
            row = bad['frames'][250]
            target = row['signal'] if key in ('authority_source','inventory_verified','official_authority_review_pending','mount_source','mount_m','mount_lane_id') else row['vehicle'] if key in ('lane_id','yaw_deg','proposed_lane_id','body_vertices_m') else row
            target.pop(key)
            try:
                measure(bad)
            except (ValueError, TypeError, KeyError):
                pass
            else:
                raise AssertionError(f'accepted absent {key}')
        straddling=packet()
        straddling['frames'][250]['vehicle']['body_vertices_m'][0][1]=-4.0
        try:
            measure(straddling)
        except ValueError as exc:
            assert 'actor body' in str(exc)
        else:
            raise AssertionError('accepted body straddling the adjacent lane')
        class V:
            def __init__(self,x=0): self.x=x; self.y=-1.75; self.z=0.0
        class B:
            def get_world_vertices(self,pose): return [V(i) for i in range(8)]
        class A:
            id=7
            type_id='vehicle.test'
            bounding_box=B()
            def get_transform(self):
                class Pose:
                    class Rotation: yaw=0.0
                    rotation=Rotation()
                return Pose()
        class W: lane_id=-1
        inventory={'id':100,'authority_source':'map_signal_inventory','inventory_verified':True,
                   'mount_source':'map_signal_transform','mount_m':[30.0,-1.75,4.5],
                   'lane_id':-1,'mount_lane_id':-1,'facing_yaw_deg':0.0}
        native=source_row(0,6000,1.25,A(),{'source':'native_signal_state','signal_id':100,
                         'indication':'green_down_arrow'},inventory,W(),-1)
        integrated=packet()
        for row in integrated['frames']:
            row['native_frame'] += 1000
            row['time_s'] += 1.25
        integrated['frames'][0]=native
        assert measure(integrated)['facing_green_proposed_frames']==600
        bad_inventory=copy.deepcopy(inventory)
        bad_inventory['inventory_verified']=False
        try:
            source_row(0,6000,1.25,A(),{'source':'native_signal_state','signal_id':100,
                       'indication':'green_down_arrow'},bad_inventory,W(),-1)
        except ValueError:
            pass
        else:
            raise AssertionError('accepted unverified original map inventory')
        print(json.dumps({'passed':True,'frames':600,'rate_hz':20,
                          'positive':{'facing_green_proposed_frames':600,
                                      'source_packet_sha256':baseline['source_packet_sha256']},
                          'comparisons':{'proposed_other_lane':mismatch['facing_green_proposed_frames'],
                                         'driver_not_facing':reversed_driver['facing_green_proposed_frames'],
                                         'red_x_distinct':red['red_x_frames']},
                          'negative_missing_source_fields':probes,
                          'negative_body_straddles_adjacent_lane':True,
                          'native_source_row_join':True,
                          'native_map_signal_readback':True,
                          'capture_static_plan':True,
                          'generic_green_rejected':True,
                          'scope':'source-shaped diagnostic only; no CARLA or legal conclusion'},sort_keys=True))

if __name__ == '__main__':
    main()
