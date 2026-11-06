"""Four unselected stop/camera constructions and predeclared measured triggers."""
from geometry import STOP_X_M

NAMES=('primary','fallback1','fallback2','fallback3')


def parameters(suffix,candidate):
    if suffix not in STOP_X_M or candidate not in NAMES:
        raise ValueError('Unknown exact case or candidate')
    value={'start_x_m':-45,'stop_x_m':STOP_X_M[suffix],
           'approach_speed_mps':5.0,'braking_start_m':6.0,
           'settle_speed_mps':.1,'settle_duration_s':2.0,
           'camera_profile':'standard'}
    if candidate=='fallback1':value['start_x_m']=-55
    if candidate=='fallback2':value['braking_start_m']=9.0
    if candidate=='fallback3':value['camera_profile']='wide'
    return value


TRIGGERS={
 'fallback1':{'source':'original Native pose/stop trace',
              'metric':'available approach distance before the entrance',
              'failure_condition':'primary spawn-to-stop clearance below 25 m or route setup fails',
              'changed_knobs':['approach start -45 m to -55 m']},
 'fallback2':{'source':'original Native pose, velocity and body trace',
              'metric':'settled stop-target longitudinal error',
              'failure_condition':'absolute stop-position error exceeds 0.25 m or 2 s stationary interval is absent',
              'changed_knobs':['braking onset 6 m to 9 m before target']},
 'fallback3':{'source':'four original source videos and frame map',
              'metric':'visible body and complete entrance corridor fraction during stationary frames',
              'failure_condition':'fraction below 0.95 in any required view',
              'changed_knobs':['overview/entrance FOV 90 to 105 degrees and elevated mount']}}
