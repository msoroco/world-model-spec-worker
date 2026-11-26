"""CPU proof of the authored Class 1 electric-bicycle command model."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from ebike import ASSIST_CUTOFF_MPS, ClassOneSpecification, drive_step
import runner_ebike


def main():
    assert runner_ebike.check()['selected_statutory_subject'] == 'electric_bicycle'
    spec = ClassOneSpecification()
    speed = 0.0
    positions = []
    for frame in range(600):
        command = drive_step(speed, 70, .05, spec)
        speed = command['speed_mps']
        assert 0 <= command['assist_power_watts'] <= 750
        assert speed <= ASSIST_CUTOFF_MPS
        positions.append((positions[-1] if positions else -25) + speed * .05)
    assert positions[0] < -24
    assert positions[450] > 3 * 450 * .05 + 2
    assert drive_step(5, 0, .05, spec)['assist_power_watts'] == 0
    assert drive_step(ASSIST_CUTOFF_MPS, 70, .05, spec)['assist_power_watts'] == 0
    for wrong in (ClassOneSpecification(motor_rated_watts=751),
                  ClassOneSpecification(operable_pedals=False),
                  ClassOneSpecification(electric_scooter=True)):
        try:
            wrong.validate()
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid electric-bicycle specification accepted')
    print(json.dumps({'passed': True, 'frames': 600,
                      'speed_end_mps': round(speed, 6),
                      'pass_margin_at_22_5_s_m': round(positions[450] -
                                                     3 * 450 * .05, 6),
                      'negative_controls': 5,
                      'physical_motor_verified': False,
                      'native_asset_classification_verified': False}, sort_keys=True))


if __name__ == '__main__':
    main()
