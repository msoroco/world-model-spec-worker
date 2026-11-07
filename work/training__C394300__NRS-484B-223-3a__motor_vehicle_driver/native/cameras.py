"""Proposed four-view 3(a) capture policy; original pixel coverage unverified."""


def camera_plan(candidate):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate')
    wide=candidate=='fallback3'
    return [
        {'name':'overview','width':1920,'height':1080,'fov_deg':80,
         'attachment':'world','xyz_m':[10,-30,48],'pitch_deg':-65,
         'purpose':'both left-turn opportunities and intervening center lane'},
        {'name':'approach','width':1280,'height':720,'fov_deg':110 if wide else 90,
         'attachment':'world','xyz_m':[-15,-15,10 if wide else 8],'pitch_deg':-28,
         'purpose':'center lane entry, first opportunity and body movement'},
        {'name':'reference_corner','width':1280,'height':720,'fov_deg':105,
         'attachment':'world','xyz_m':[43,-18,12],'pitch_deg':-35,
         'purpose':'later through-lane exit and left turn'},
        {'name':'driver_reference','width':1280,'height':720,'fov_deg':105,
         'attachment':'ego','xyz_m':[1,0,1.5],'pitch_deg':-2,
         'purpose':'subject forward reference; no driver intent proof'}]
