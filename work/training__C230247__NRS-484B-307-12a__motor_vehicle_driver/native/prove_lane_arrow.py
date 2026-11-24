"""Run 30-second source-shaped diagnostic and negative probes on the meter."""
import copy
import json
import tempfile
from pathlib import Path
from lane_arrow_meter import measure, measure_file


def packet(signal_lane=-1, proposed_lane=-1, indication='green_down_arrow', yaw=0.0):
    return {'format':'synthetic-source-shaped-diagnostic', 'frames':[
        {'frame':i,'native_frame':5000+i,'time_s':round(i/20,3),'source':'native_post_tick',
         'signal':{'source':'native_signal_state','authority_source':'map_signal_inventory',
                   'mount_source':'map_signal_transform','lane_id':signal_lane,
                   'mount_lane_id':signal_lane,'facing_yaw_deg':0.0,'indication':indication},
         'vehicle':{'source':'native_actor_pose','lane_source':'map_waypoint_projection',
                    'lane_id':-1,'proposed_lane_id':proposed_lane,'yaw_deg':yaw}}
        for i in range(600)]}


def main():
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp)/'source.json'
        source.write_text(json.dumps(packet(),separators=(',',':'))+'\n')
        baseline = measure_file(source)
        assert baseline['frames'] == 600 and baseline['facing_green_proposed_frames'] == 600
        assert baseline['facing_green_occupied_frames'] == 600
        mismatch = measure(packet(proposed_lane=-2))
        assert mismatch['facing_green_proposed_frames'] == 0 and mismatch['facing_green_occupied_frames'] == 600
        reversed_driver = measure(packet(yaw=180))
        assert reversed_driver['facing_green_proposed_frames'] == 0
        red = measure(packet(indication='red_x'))
        assert red['red_x_frames'] == 600 and red['facing_green_proposed_frames'] == 0
        probes = ['source','authority_source','mount_source','mount_lane_id','lane_id','yaw_deg','proposed_lane_id','native_frame','time_s']
        for key in probes:
            bad = packet()
            row = bad['frames'][250]
            target = row['signal'] if key in ('authority_source','mount_source','mount_lane_id') else row['vehicle'] if key in ('lane_id','yaw_deg','proposed_lane_id') else row
            target.pop(key)
            try:
                measure(bad)
            except (ValueError, TypeError, KeyError):
                pass
            else:
                raise AssertionError(f'accepted absent {key}')
        print(json.dumps({'passed':True,'frames':600,'rate_hz':20,
                          'positive':{'facing_green_proposed_frames':600,
                                      'source_packet_sha256':baseline['source_packet_sha256']},
                          'comparisons':{'proposed_other_lane':mismatch['facing_green_proposed_frames'],
                                         'driver_not_facing':reversed_driver['facing_green_proposed_frames'],
                                         'red_x_distinct':red['red_x_frames']},
                          'negative_missing_source_fields':probes,
                          'scope':'source-shaped diagnostic only; no CARLA or legal conclusion'},sort_keys=True))

if __name__ == '__main__':
    main()
