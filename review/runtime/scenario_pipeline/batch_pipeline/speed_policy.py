"""Physical speed probe defaults; these margins never change a legal threshold."""
import math
import re

MPH_MPS = 0.44704
FACTORS = {'m/s': 1., 'mph': MPH_MPS, 'km/h': 1/3.6, 'kmh': 1/3.6}


def speed_targets(threshold, unit, operator, margin_mph=5., middle_margin_mph=.5,
                  override_reason=None):
    if unit not in FACTORS or operator not in ('>', '>=', '<', '<='):
        raise ValueError('Unsupported speed threshold unit/operator')
    if margin_mph != 5. and not override_reason:
        raise ValueError('Nondefault speed margin needs an override reason')
    if not 0 < middle_margin_mph < margin_mph:
        raise ValueError('Middle offset must be positive and smaller than outer margin')
    delta = margin_mph * MPH_MPS / FACTORS[unit]
    inner = middle_margin_mph * MPH_MPS / FACTORS[unit]
    if threshold-delta < 0:
        raise ValueError('Low-speed threshold needs an explicit smaller margin override')
    return {'below': threshold-delta,
            'at': threshold-inner if operator in ('>', '>=') else threshold+inner,
            'above': threshold+delta}


def apply_speed_policy(cases, templates):
    from .validation import numeric_thresholds
    by_law = {t['law_id']: t for t in templates}
    for case in cases:
        probe = case.get('probe', {})
        if case.get('target_type') != 'boundary_probe' or probe.get('primary_variable') != 'ego_speed':
            continue
        template = by_law.get(case['target_law_id'])
        if template is None:
            continue
        matches = [t for ref, t in numeric_thresholds(template, case['variable_assignments'])
                   if ref == probe['threshold_ref']]
        if len(matches) != 1:
            raise ValueError('Speed probe has no unique resolved threshold')
        threshold = matches[0]
        branch = case.get('speed_probe_policy',{}).get('branch',re.split(r'[-_]',case['case_id'])[-1])
        if branch not in ('below', 'at', 'above'):
            named=probe.get('target_value_or_branch')
            named=named.get('branch') if isinstance(named,dict) else named
            if named in ('below','at','above'):branch=named
            else:
                original=probe['test_value']
                branch='below' if original<threshold['value'] else 'above' if original>threshold['value'] else 'at'
        policy = case.get('speed_probe_policy', {})
        margin = policy.get('margin_mph', 5.)
        inner = policy.get('middle_margin_mph', .5)
        targets = speed_targets(threshold['value'], threshold['unit'], threshold['operator'],
                                margin, inner, policy.get('override_reason'))
        value = targets[branch]
        case['speed_probe_policy'] = dict(policy, margin_mph=margin, middle_margin_mph=inner,
            threshold=threshold['value'], unit=threshold['unit'], operator=threshold['operator'],
            branch=branch, middle_semantics='inside compliant side; not exact equality')
        probe.update(test_value=value, unit=threshold['unit'], operator=threshold['operator'])
        case['variable_assignments']['commanded_approach_speed']['value'] = value * FACTORS[threshold['unit']]
        epsilon = {'value': margin*MPH_MPS/FACTORS[threshold['unit']], 'unit': threshold['unit'],
                   'rationale': policy.get('override_reason') or 'General physical speed margin of 5 mph; not legal tolerance.'}
        case['epsilon_used'] = epsilon
        probe['epsilon_used'] = epsilon


def probe_branch(case, threshold):
    value = case['probe']['test_value']
    policy = case.get('speed_probe_policy')
    if policy:
        if case['probe']['primary_variable'] != 'ego_speed':
            raise ValueError('Speed policy cannot authorize another observable')
        if policy['threshold'] != threshold['value'] or policy['unit'] != threshold['unit'] or policy['operator'] != threshold['operator']:
            raise ValueError('Speed policy differs from resolved legal threshold')
        expected = speed_targets(threshold['value'], threshold['unit'], threshold['operator'],
                                 policy['margin_mph'], policy['middle_margin_mph'], policy.get('override_reason'))
        branch = policy['branch']
        if branch not in expected or not math.isclose(value, expected[branch], abs_tol=1e-10, rel_tol=0):
            raise ValueError('Speed probe differs from declared physical margin')
        requested = case['variable_assignments']['commanded_approach_speed']['value']
        if not math.isclose(requested, value*FACTORS[threshold['unit']], abs_tol=1e-10, rel_tol=0):
            raise ValueError('Speed controller target has inconsistent units')
        return branch
    return 'below' if value < threshold['value'] else 'above' if value > threshold['value'] else 'at'
