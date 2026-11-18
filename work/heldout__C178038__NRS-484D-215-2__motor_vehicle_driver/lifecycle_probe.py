"""Check prospective capture-to-saved-processing event ordering in CPU fixtures."""

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def verify(events):
    if events != EVENTS:
        raise ValueError('Saved processing must follow encoder closure, restoration and owner release')
    return True


if __name__ == '__main__':
    assert verify(EVENTS)
    try:
        verify(EVENTS[:3] + EVENTS[4:5] + EVENTS[3:4] + EVENTS[5:])
    except ValueError:
        pass
    else:
        raise ValueError('Out-of-order owner release was accepted')
    print('synthetic lifecycle ordering and negative test passed')
