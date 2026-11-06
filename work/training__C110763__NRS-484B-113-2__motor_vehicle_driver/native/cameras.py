"""Four synchronized reverse/intersection views; original pixels pending."""
def camera_plan(candidate='primary'):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown camera candidate')
    fov=105 if candidate=='fallback3' else 90
    return [
        {'name':'overview','width':1920,'height':1080,'fov_deg':fov,
         'attachment':'world','xyz_m':[10,-18,35],'pitch_deg':-65},
        {'name':'approach','width':1280,'height':720,'fov_deg':90,
         'attachment':'world','xyz_m':[17,-10,12],'pitch_deg':-40},
        {'name':'intersection','width':1280,'height':720,'fov_deg':90,
         'attachment':'world','xyz_m':[5,-12,12],'pitch_deg':-55},
        {'name':'reverse','width':1280,'height':720,'fov_deg':90,
         'attachment':'world','xyz_m':[3,-8,10],'pitch_deg':-40},
    ]
