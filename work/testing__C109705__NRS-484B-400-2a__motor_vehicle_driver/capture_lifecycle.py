"""Gate saved processing on release of Native capture resources."""


EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def run(capture_action, process_saved_action, owner):
    """Run saved processing only after the Native owner certifies full closure.

    The owner provides observed booleans after capture_action returns. A false
    observation stops the handoff before process_saved_action is called.
    """
    captured = capture_action()
    events = ['capture_finished']
    for field, event in (('encoders_closed', 'encoders_closed'),
                         ('restoration_verified', 'restoration_verified'),
                         ('native_exited', 'native_exit'),
                         ('owner_released', 'owner_released')):
        if getattr(owner, field, False) is not True:
            raise RuntimeError('Native lifecycle incomplete: ' + event)
        events.append(event)
    events.append('saved_processing_started')
    processed = process_saved_action(captured)
    return {'events': events, 'capture': captured, 'processed': processed}
