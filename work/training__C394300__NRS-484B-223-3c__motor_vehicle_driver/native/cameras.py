"""Four synchronized camera policies; actual pixel framing is unverified."""
PROFILE='overview1080-capability-v1'
RATE_HZ=20


def camera_plan(candidate='primary'):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate')
    wide=candidate=='fallback3'
    return [
        {'name':'overview','width':1920,'height':1080,'fov_deg':85,
         'attachment':'world','xyz_m':[-42,20,45],'pitch_deg':-62,
         'purpose':'inbound left turn, center lane, merge and complete ego body'},
        {'name':'approach','width':1280,'height':720,'fov_deg':105 if wide else 90,
         'attachment':'ego','xyz_m':[-8,0,4.5 if wide else 3.2],'pitch_deg':-17,
         'purpose':'lane marking, merge onset and complete ego body'},
        {'name':'reference_corner','width':1280,'height':720,'fov_deg':105 if wide else 90,
         'attachment':'world','xyz_m':[-62,8,12],'pitch_deg':-30,
         'purpose':'left turn completion and center-lane/through-lane boundary'},
        {'name':'driver_reference','width':1280,'height':720,'fov_deg':105,
         'attachment':'ego','xyz_m':[1,0,1.5],'pitch_deg':-2,
         'purpose':'subject forward reference; does not prove perception'},
    ]
