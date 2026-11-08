"""Authored bicycle-lane propulsion-test path for disabled/healthy controls."""
from alley_geometry import check as map_check,open_drive

def route():
    return ((0.0,-4.0),(5.0,-4.0),(10.0,-4.0),(15.0,-4.0))

def check():
    map_check()
    path=route()
    if any(not (-5.0<y<-3.0) for x,y in path):
        raise ValueError('Propulsion-test path leaves authored bicycle lane')
    return {'route_points':len(path),'native_map_authored':True,'original_native_readback':False}
