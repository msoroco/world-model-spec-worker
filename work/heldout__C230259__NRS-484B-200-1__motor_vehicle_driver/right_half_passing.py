"""Connected right-to-left-to-right overtaking targets on a two-way road."""
from math import hypot
from road_source_capture import _opposing_neighbor, _xy


def passing_targets(route, *, lead_index=8, left_entry_index=5, left_exit_index=12):
    """Return a geometric controller path; physical passing-law facts stay undecided.

    The left excursion begins before the slower lead and ends after its route
    station. Native execution must independently verify approach, clearance,
    return and any governing passing-law context.
    """
    if len(route) < 17 or not (2 < left_entry_index < lead_index < left_exit_index < len(route)-2):
        raise ValueError('Passing route needs connected approach, lead and return stations')
    targets=[]
    for i,waypoint in enumerate(route):
        right=_xy(waypoint.transform.location)
        left=_xy(_opposing_neighbor(waypoint).transform.location)
        if i<=2 or i>=left_exit_index+2:
            fraction=0.
        elif i<left_entry_index:
            fraction=(i-2)/(left_entry_index-2)
        elif i<=left_exit_index:
            fraction=1.
        else:
            fraction=(left_exit_index+2-i)/2
        target=[right[0]+fraction*(left[0]-right[0]),
                right[1]+fraction*(left[1]-right[1])]
        targets.append(target)
    if any(hypot(b[0]-a[0],b[1]-a[1])<0.25 for a,b in zip(targets,targets[1:])):
        raise ValueError('Passing targets contain a stationary controller step')
    if not (all(targets[i]==list(_xy(route[i].transform.location)) for i in (0,1,2,len(route)-2,len(route)-1)) and
            targets[lead_index]==list(_xy(_opposing_neighbor(route[lead_index]).transform.location))):
        raise ValueError('Passing geometry did not leave and return to right half')
    return {'targets_xy_m':targets,'lead_spawn_xy_m':list(_xy(route[lead_index].transform.location)),
            'lead_index':lead_index,'left_entry_index':left_entry_index,
            'left_exit_index':left_exit_index,
            'physical_passing_confirmed':False,'governing_law_decided':False}
