"""Instantaneous reflected horizontal-heading rate from original world angular velocity."""
import math

METHOD = 'original_world_angular_velocity_horizontal_heading_derivative_v1'


def horizontal_heading_rate(observation):
    """Differentiate atan2(-fy, fx); require actual 3-D forward and world-axis degrees/s.

    With df/dt = omega cross f, this is -wz + fz*(wx*fx+wy*fy)/(fx²+fy²).
    Degrees/s stays degrees/s because the radian conversions cancel. This is
    distinct from a sampled heading finite difference, especially near vertical.
    """
    provenance = {'method': METHOD}
    if observation.get('acquisition') in ('recorder_replay', 'replay'):
        return None, dict(provenance, gap='replay-only angular velocity')
    def vector(name):
        value = observation.get(name)
        if value is None:return None
        if not isinstance(value, (list, tuple)) or len(value) != 3 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in value):
            raise ValueError('Invalid original angular/forward vector: '+name)
        return [float(v) for v in value]
    angular = vector('angular_velocity_deg_s')
    forward = vector('forward_vector')
    if angular is None or forward is None:
        return None, dict(provenance, gap='missing original angular velocity or 3-D forward vector')
    if observation.get('angular_velocity_frame') != 'world':
        return None, dict(provenance, gap='unverified angular vector coordinate frame')
    fx, fy, fz = forward
    norm = math.hypot(fx, fy)
    if norm == 0 or not math.isfinite(norm):
        return None, dict(provenance, gap='undefined horizontal heading')
    wx, wy, wz = angular
    value = -wz + (fz/norm)*(wx*(fx/norm)+wy*(fy/norm))
    if not math.isfinite(value):
        return None, dict(provenance, gap='nonfinite horizontal heading-rate projection')
    provenance.update(value_deg_s=value, angular_velocity_frame='world',
                      horizontal_forward_norm=norm, source='original_world_angular_velocity_and_3D_forward',
                      reflected_output_y_axis=True)
    return value, provenance
