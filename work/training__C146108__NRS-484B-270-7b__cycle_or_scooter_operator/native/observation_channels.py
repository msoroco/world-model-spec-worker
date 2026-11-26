"""Exact source-observation channels for the rider's full pass."""


def channels():
    common = {'sampling_rate_hz': 20,
              'time_window': 'entire 600-frame 30-second pass',
              'reference_frame': 'original Native frame and authored road',
              'uncertainty': '50 ms sampling; physical semantics need review'}
    specs = (
        ('drv.overtaking', 'structured event', 'joined rider/motor full-body behind, alongside and clear-ahead order'),
        ('ru.motor_vehicle', 'structured identity', 'original Native other actor identity and pass context'),
        ('rel.surface_gap', 'm', 'minimum original full-body pass separation'),
        ('drv.time_to_conflict', 's', 'initial pose-derived time to rear-body overlap'),
        ('drv.passing_side', 'categorical', 'rider lateral side at first alongside frame'),
        ('kin.speed', 'm/s', 'original rider and motor pose-derived closing speed'),
        ('ru.occupant_count', 'count', 'sourced driver count with cabin review unresolved'),
    )
    return [dict(name=name, unit=unit, method=method, **common)
            for name, unit, method in specs]
