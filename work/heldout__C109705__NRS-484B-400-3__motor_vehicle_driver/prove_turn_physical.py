"""Exercise source-only complete, incomplete and missing turn protocol branches."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from turn_physical_probe import assess


CASES=(
 'heldout__C109705__NRS-484B-400-3__motor_vehicle_driver__centerline_approach_left_curb_departure',
 'heldout__C109705__NRS-484B-400-3__motor_vehicle_driver__farther_approach_left_curb_departure',
 'heldout__C109705__NRS-484B-400-3__motor_vehicle_driver__centerline_approach_farther_departure')


def write(root, case, positions):
    geometry={'case_id':case,'ego_actor_id':7,'approach_directions':2,
        'destination_directions':1,'maneuver':'left_turn',
        'intersection_kind':'public_highway_non_alley',
        'approach_centerline_xy_m':[[0,-10],[0,0]],
        'destination_left_curb_xy_m':[[0,-3],[-10,-3]],
        'intersection_entry_xy_m':[0,0]}
    (root/'turn_road_geometry.json').write_text(json.dumps(geometry)+'\n')
    rows=[];frames=[]
    for index,(x,y) in enumerate(positions):
        rows.append({'frame':100+index,'time_s':index/20,'actor_id':7,
            'phase':('approach','entry','departure')[index],
            'body_corners_xy_m':[[x,y],[x+.4,y],[x+.4,y+.4],[x,y+.4]]})
        frames.append({'video_frame':index,'carla_frame':100+index,'time_s':index/20})
    (root/'body_footprints.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))


def main():
    for case in CASES:
        with TemporaryDirectory() as directory:
            root=Path(directory)
            write(root,case,[(.5,-2),(.5,-1),(-1,0)])
            complete=assess(root,case)
            if complete['status']!='met':raise ValueError('Complete original turn motion rejected')
            write(root,case,[(.5,-2),(.5,-2),(.5,-2)])
            incomplete=assess(root,case)
            if incomplete['status']!='not_met':raise ValueError('Stationary turn incorrectly complete')
            (root/'body_footprints.jsonl').unlink()
            try:assess(root,case)
            except ValueError as error:
                if 'Missing original turn source' not in str(error):raise
            else:raise ValueError('Missing original turn body was accepted')
        print(case+': complete, stationary, missing-original pass')


if __name__=='__main__':main()
