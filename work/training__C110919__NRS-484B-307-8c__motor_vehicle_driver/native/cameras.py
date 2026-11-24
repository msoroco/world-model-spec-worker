"""Four lossless original-frame camera proposals; pixel coverage unverified."""

def camera_plan(candidate: str):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate')
    fov=105 if candidate=='fallback3' else 90
    return [
        {'name':'overview','width':1920,'height':1080,'fov_deg':fov,
         'attachment':'world','xyz_m':[20,-24,40], 'purpose':'signal, full body, right turn, pedestrian'},
        {'name':'approach','width':1280,'height':720,'fov_deg':90,
         'attachment':'world','xyz_m':[9,-22,14], 'purpose':'stop line and first crosswalk'},
        {'name':'reference_corner','width':1280,'height':720,'fov_deg':85,
         'attachment':'ego','xyz_m':[1.0,0,1.7], 'purpose':'governing red signal'},
        {'name':'driver_reference','width':1280,'height':720,'fov_deg':90,
         'attachment':'world','xyz_m':[14,8,12], 'purpose':'pedestrian clearance at destination crosswalk'},
    ]
