"""Authored Class 1 assist surrogate for the frozen electric-bicycle witness.

This models a drivetrain command, not a certified physical CARLA asset. The
carrier bicycle's rendered pedals and motor cannot independently establish its
legal classification; that limitation must survive into the delivery review.
"""
from dataclasses import dataclass
import math


MPH_TO_MPS = 0.44704
ASSIST_CUTOFF_MPS = 20 * MPH_TO_MPS


@dataclass(frozen=True)
class ClassOneSpecification:
    wheels: int = 2
    operable_pedals: bool = True
    saddle: bool = True
    motor_rated_watts: float = 500.0
    pedal_power_watts: float = 175.0
    rider_and_bicycle_mass_kg: float = 95.0
    moped: bool = False
    electric_scooter: bool = False

    def validate(self):
        if self.wheels not in (2, 3) or not self.operable_pedals or not self.saddle:
            raise ValueError('Electric-bicycle geometry or operable pedals absent')
        if self.moped or self.electric_scooter:
            raise ValueError('Wrong statutory rider class')
        if not (0 < self.motor_rated_watts <= 750):
            raise ValueError('Class 1 motor rating exceeds 750 watts')
        if not (0 < self.pedal_power_watts < 1000 and self.rider_and_bicycle_mass_kg > 0):
            raise ValueError('Invalid authored drivetrain parameters')


def drive_step(speed_mps, pedal_cadence_rpm, dt_s, specification=None):
    """Return next kinematic speed and sourced power command at one fixed tick."""
    spec = specification or ClassOneSpecification()
    spec.validate()
    if not all(math.isfinite(x) for x in (speed_mps, pedal_cadence_rpm, dt_s)):
        raise ValueError('Nonfinite drivetrain input')
    if speed_mps < 0 or pedal_cadence_rpm < 0 or dt_s <= 0 or dt_s > 0.1:
        raise ValueError('Invalid drivetrain input')
    pedaling = pedal_cadence_rpm > 0
    pedal_watts = spec.pedal_power_watts if pedaling else 0.0
    assist_watts = (spec.motor_rated_watts if pedaling and
                    speed_mps < ASSIST_CUTOFF_MPS else 0.0)
    # 1 m/s denominator bounds the low-speed force command. This is an
    # authored surrogate, not an inference of physical motor torque.
    propulsive_force_n = (pedal_watts + assist_watts) / max(speed_mps, 1.0)
    resistance_n = 10.0 + 0.3 * speed_mps * speed_mps
    next_speed = max(0.0, speed_mps +
                     (propulsive_force_n - resistance_n) * dt_s /
                     spec.rider_and_bicycle_mass_kg)
    return {'speed_mps': min(next_speed, ASSIST_CUTOFF_MPS),
            'pedaling': pedaling, 'pedal_cadence_rpm': pedal_cadence_rpm,
            'pedal_power_watts': pedal_watts, 'assist_power_watts': assist_watts,
            'assist_cutoff_mps': ASSIST_CUTOFF_MPS,
            'power_source': 'authored Class 1 kinematic surrogate'}
