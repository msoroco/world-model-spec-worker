"""Unselected exception-A turn candidates and measured fallback conditions."""


def parameters(candidate):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown alley turn candidate')
    values={'approach_start_x_m':-45.0,'turn_speed_mps':2.5,
            'turn_radius_m':5.0,'camera_profile':'standard'}
    if candidate=='fallback1':values['approach_start_x_m']=-55.0
    if candidate=='fallback2':values['turn_speed_mps']=1.8
    if candidate=='fallback3':values['camera_profile']='wide_alley_view'
    return values


TRIGGERS={
    'fallback1':{'source':'original Native pose and authored turn station',
        'metric':'approach runway before turn (m)',
        'failure_condition':'measured runway < 35 m',
        'changed_knobs':['approach start x -45 m to -55 m']},
    'fallback2':{'source':'original Native turn velocity and route radius',
        'metric':'peak v squared / radius (m/s2) during turn',
        'failure_condition':'measured lateral acceleration proxy > 1.5 m/s2',
        'changed_knobs':['turn target speed 2.5 to 1.8 m/s']},
    'fallback3':{'source':'original facility and alley camera frames joined to Native turn interval',
        'metric':'visible turn frames / all turn frames',
        'failure_condition':'measured visible fraction < 0.95',
        'changed_knobs':['facility camera to wide elevated alley view']}}
