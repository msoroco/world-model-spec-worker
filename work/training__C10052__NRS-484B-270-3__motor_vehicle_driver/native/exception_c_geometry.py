"""Proposed Native routes for traffic-conflict avoidance and absence control."""
from alley_geometry import check as map_check, open_drive

def route(start, response, diversion_start_frame):
    if response not in ('avoid','no_conflict') or start not in (-50.0,-60.0):
        raise ValueError('Unknown conflict-avoidance route')
    if diversion_start_frame not in (130,140):raise ValueError('Unknown diversion timing')
    if response=='no_conflict':
        return ((start,-1.5),(-25,-1.5),(0,-1.5),(25,-1.5),(55,-1.5))
    departure=-17.5 if diversion_start_frame==130 else -15.0
    return ((start,-1.5),(departure-5,-1.5),(departure,-4.0),
            (15,-4.0),(25,-1.5),(55,-1.5))

def check():
    map_check()
    for start in (-50.0,-60.0):
        for shift in (130,140):
            avoid=route(start,'avoid',shift)
            clear=route(start,'no_conflict',shift)
            assert any(y==-4.0 for x,y in avoid)
            assert all(y==-1.5 for x,y in clear)
            assert avoid[0]==clear[0]
    return {'routes':8,'native_map_authored':True,'original_native_readback':False}

if __name__=='__main__':
    import json
    print(json.dumps(check()))
