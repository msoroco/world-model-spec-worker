"""Request the left indicator from the authored onset station onward."""
import math


def left_signal_requested(observed_x_m: float, onset_x_m: float) -> bool:
    if not math.isfinite(observed_x_m) or not math.isfinite(onset_x_m):
        raise ValueError("Nonfinite observed pose or signal station")
    return observed_x_m >= onset_x_m
