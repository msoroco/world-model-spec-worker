"""Four lossless original-frame camera proposals; pixel coverage unverified."""

def camera_plan(candidate: str):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate')
    fov=105 if candidate=='fallback3' else 90
    return [
        {'name':'overview','width':1920,'height':1080,'fov_deg':fov,
         'attachment':'world','xyz_m':[20,-24,40], 'purpose':'uncontrolled crossing, full body and pedestrian'},
        {'name':'approach','width':1280,'height':720,'fov_deg':90,
         'attachment':'world','xyz_m':[9,-22,14], 'purpose':'marked crosswalk and ego directional half'},
        {'name':'signal','width':1280,'height':720,'fov_deg':85,
         'attachment':'ego','xyz_m':[1.0,0,1.7], 'purpose':'official-device absence and forward crosswalk view'},
        {'name':'destination','width':1280,'height':720,'fov_deg':90,
         'attachment':'world','xyz_m':[14,8,12], 'purpose':'pedestrian occupancy and white-cane visual verification'},
    ]
