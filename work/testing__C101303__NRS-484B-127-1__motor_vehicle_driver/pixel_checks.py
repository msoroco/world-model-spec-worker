"""Decoded nonblank pixel check; participant visibility needs physical review."""


def check(frame):
    if not any(frame.pixels):
        raise ValueError('decoded frame contains no visible pixel information')
