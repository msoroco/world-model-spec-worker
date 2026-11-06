"""Four lossless original-frame camera proposals; pixel coverage unverified."""

def camera_plan(candidate: str):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate')
    fov=105 if candidate=='fallback3' else 90
    return [
        {'name':'overview','width':1920,'height':1080,'fov_deg':fov,
         'attachment':'world','xyz_m':[20,-24,40], 'purpose':'both full bodies and intersection conflict zone'},
        {'name':'bicycle_approach','width':1280,'height':720,'fov_deg':90,
         'attachment':'world','xyz_m':[9,-22,14], 'purpose':'bicycle class, rider and approach route'},
        {'name':'motorist_approach','width':1280,'height':720,'fov_deg':85,
         'attachment':'world','xyz_m':[-22,9,14], 'purpose':'separate motor vehicle and brake response'},
        {'name':'conflict','width':1280,'height':720,'fov_deg':90,
         'attachment':'world','xyz_m':[14,8,12], 'purpose':'body clearance and time joined interaction'},
    ]
