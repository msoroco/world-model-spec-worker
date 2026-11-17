"""Signed acceleration along normalized horizontal body heading, m/s²."""
import math

METHOD = 'normalized_horizontal_heading_dot_v1'


def horizontal_acceleration(observation):
    """Return value and provenance; unversioned/3-D scalars never become horizontal."""
    provenance = {'method': METHOD, 'scalar_method': observation.get('acceleration_method', 'unversioned_scalar') if observation.get('accel_longitudinal_mps2') is not None else None}
    if 'accel_longitudinal_mps2' in observation:
        provenance['retained_scalar_mps2'] = observation['accel_longitudinal_mps2']
        if provenance['scalar_method'] != METHOD:
            provenance['scalar_status'] = 'different_or_unverified_method_not_compared'
    if observation.get('acquisition') in ('recorder_replay', 'replay'):
        return None, dict(provenance, gap='replay-only acceleration')
    def vector(name, lengths):
        value = observation.get(name)
        if value is None:return None
        if not isinstance(value, (list, tuple)) or len(value) not in lengths or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
            raise ValueError('Invalid original acceleration/heading vector: '+name)
        return value
    acceleration = vector('acceleration_mps2', (3,))
    heading = vector('heading_xy', (2,))
    if heading is None:
        forward = vector('forward_vector', (3,))
        if forward is not None:heading = forward[:2]
    if heading is None and observation.get('heading_deg') is not None:
        angle = observation['heading_deg']
        if type(angle) not in (int,float) or not math.isfinite(angle):raise ValueError('Invalid original heading')
        heading = [math.cos(math.radians(angle)), math.sin(math.radians(angle))]
    value = None
    if heading is not None:
        norm = math.hypot(*heading)
        if not math.isfinite(norm) or norm == 0:
            raise ValueError('Original horizontal heading norm must be finite and nonzero')
        hx, hy = heading[0]/norm, heading[1]/norm
        if acceleration is not None:
            value = acceleration[0]*hx + acceleration[1]*hy
            if not math.isfinite(value):raise ValueError('Nonfinite horizontal acceleration projection')
    scalar = observation.get('accel_longitudinal_mps2')
    if scalar is not None and (type(scalar) not in (int,float) or not math.isfinite(scalar)):
        raise ValueError('Invalid original longitudinal acceleration')
    bound = observation.get('acceleration_quantization_bound_mps2')
    if bound is not None and (type(bound) not in (int,float) or not math.isfinite(bound) or bound < 0):
        raise ValueError('Invalid declared acceleration quantization bound')
    unresolved = observation.get('acceleration_rounded') is True and bound is None
    provenance.update(source='vectors' if value is not None else 'scalar', quantization_bound_mps2=bound,
                      comparison_unresolved=unresolved)
    if scalar is not None and provenance['scalar_method'] == METHOD:
        if value is not None and not unresolved and abs(value-scalar) > 1e-6+(bound or 0):
            raise ValueError('Conflicting equivalent horizontal acceleration measurements')
        if value is None and not unresolved:value = scalar
    if value is None:provenance['gap'] = 'missing original horizontal acceleration source'
    else:provenance['value_mps2'] = value
    return value, provenance
