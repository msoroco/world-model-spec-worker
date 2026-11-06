"""Four lossless source-camera proposals for the alley entrance."""


def camera_plan(candidate):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate camera policy')
    wide=candidate=='fallback3'
    return [
        {'name':'overview','width':1920,'height':1080,'xyz_m':[-8,-12,12 if wide else 9],
         'fov_deg':105 if wide else 90,'attachment':'world'},
        {'name':'approach','width':1280,'height':720,'xyz_m':[-18,-2,5],
         'fov_deg':95,'attachment':'world'},
        {'name':'entrance','width':1280,'height':720,'xyz_m':[0,-13,8 if wide else 6],
         'fov_deg':105 if wide else 90,'attachment':'world'},
        {'name':'driver_reference','width':1280,'height':720,'xyz_m':[1,0,2.2],
         'fov_deg':90,'attachment':'ego'}]
