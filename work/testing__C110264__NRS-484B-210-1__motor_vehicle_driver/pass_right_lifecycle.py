"""Guard saved processing behind Native ownership and source closure."""
from __future__ import annotations

ORDER = ('capture_finished', 'encoders_closed', 'restoration_verified',
         'native_exit', 'owner_released', 'saved_processing_started')


def validate_order(events):
    """Require an exact local ownership release sequence before processing."""
    if not isinstance(events, list) or tuple(events) != ORDER:
        raise ValueError('saved processing began before Native ownership release')
    return {'events': list(ORDER), 'saved_processing_after_release': True}
