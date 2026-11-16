"""Four proposed source views; Native pixel coverage remains unverified."""
from __future__ import annotations

from engineering import plan
from geometry import FT_M, TURN_STATION_M, center_xy, road_height


def camera_plan(suffix: str, candidate: str) -> list[dict]:
    settings=plan(suffix,candidate)['knobs']
    center=center_xy(TURN_STATION_M)
    height=settings['reference_camera_height_m']
    views=[
      {'name':'overview','attachment':'world','width':1920,'height':1080,
       'native_xyz_m':[center[0]+18,0,road_height(TURN_STATION_M)+18],
       'fov_deg':90},
      {'name':'approach','attachment':'reference_left','width':1280,'height':720,
       'native_xyz_m':[0,0,height],'fov_deg':90},
      {'name':'reference_corner','attachment':'reference_right','width':1280,'height':720,
       'native_xyz_m':[0,0,height],'fov_deg':90},
      {'name':'driver_reference','attachment':'ego','width':1280,'height':720,
       'native_xyz_m':[0,0,settings['ego_camera_height_m']],'fov_deg':100},
    ]
    assert len({view['name'] for view in views})==4
    return views
