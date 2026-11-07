"""Onset uses measured longitudinal Native pose, with no synthetic signal claim."""
import math

def left_signal_requested(observed_native_x_m, onset_x_m):
    if not math.isfinite(observed_native_x_m) or not math.isfinite(onset_x_m):
        raise ValueError("Nonfinite signal decision")
    return observed_native_x_m >= onset_x_m
