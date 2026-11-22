"""Minimal decoded-pixel presence check; participant visibility remains physical review."""


def check(frame):
    if not any(frame.pixels):
        raise ValueError('decoded frame contains no visible pixel information')
