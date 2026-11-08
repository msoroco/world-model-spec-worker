"""Proposed Native response routes for synthetic duty/routine controls."""
from alley_geometry import check as map_check,open_drive

def route(start,response,lead_end_frame):
    if response not in ('duty','routine') or start not in (-50.0,-60.0):
        raise ValueError('Unknown duty-control route')
    if lead_end_frame not in (120,135):raise ValueError('Unknown response lead')
    if response=='routine':
        return ((start,-1.5),(-25,-1.5),(0,-1.5),(25,-1.5),(55,-1.5))
    departure=-17.5 if lead_end_frame==120 else -15.0
    return ((start,-1.5),(departure-5,-1.5),(departure,-4.0),
            (15,-4.0),(25,-1.5),(55,-1.5))

def check():
    map_check()
    for start in (-50.0,-60.0):
        for shift in (120,135):
            duty=route(start,'duty',shift)
            routine=route(start,'routine',shift)
            assert any(y==-4.0 for x,y in duty)
            assert all(y==-1.5 for x,y in routine)
            assert duty[0]==routine[0]
    return {'routes':8,'native_map_authored':True,'original_native_readback':False}

if __name__=='__main__':
    import json
    print(json.dumps(check()))
