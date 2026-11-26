"""Decoded source pixel presence; object visibility also needs source review."""


def check(frame):
    if not any(frame.pixels):
        raise ValueError("decoded original frame has no visible pixel information")
