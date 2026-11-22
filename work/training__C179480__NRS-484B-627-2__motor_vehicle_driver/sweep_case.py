"""Exact C179480 sweep case identity and single-axis binding."""

ASSIGNMENT = 'training__C179480__NRS-484B-627-2__motor_vehicle_driver'
BASE = ('reference', 'contrast', 'safe_operation_stop', 'law_required_stop')
SWEEPS = {
    'c179480-traffic-effect-gap': ('reference', 'following_gap_m', (7.0, 12.0, 9.5)),
    'c179480-safe-operation-gap': ('safe_operation_stop', 'hazard_center_gap_m', (6.0, 10.0, 8.0)),
    'c179480-governing-red-onset': ('law_required_stop', 'governing_red_onset_s', (9.0, 13.0, 11.0)),
}


def resolve(config):
    base = config.get('case_suffix')
    if base not in BASE:
        raise ValueError('Unknown C179480 base case')
    sweep = config.get('sweep')
    if sweep is None:
        if config.get('case_id') != ASSIGNMENT+'__'+base:
            raise ValueError('Base case identity differs')
        return base, None, None
    if not isinstance(sweep, dict) or set(sweep) != {'sweep_id', 'sweep_point'}:
        raise ValueError('Incomplete exact sweep binding')
    spec = SWEEPS.get(sweep['sweep_id'])
    if spec is None or spec[0] != base or not isinstance(sweep['sweep_point'], dict):
        raise ValueError('Sweep differs from its Native base case')
    _, axis, values = spec
    if set(sweep['sweep_point']) != {axis}:
        raise ValueError('Sweep must change its one reviewed axis')
    value = sweep['sweep_point'][axis]
    if type(value) not in (int, float) or value not in values:
        raise ValueError('Unreviewed sweep value')
    index = values.index(value)
    if config.get('case_id') not in (
            sweep['sweep_id']+f'-{index:04d}',
            ASSIGNMENT+'__'+sweep['sweep_id']+f'-{index:04d}'):
        raise ValueError('Exact expanded sweep case identity differs')
    return base, axis, value
