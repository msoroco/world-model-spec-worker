"""CPU proof for the draft C158190 through-speed control and body binding."""

import hashlib
import json
from pathlib import Path
from statistics import median

from through_speed_sweep import TARGETS_MPS, body_speed_samples, command_through

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT.parent.parent /
          '.runtime-work/c158190-yield_nearest_view_through_approaches-primary-stable-v1-compat/interaction_history.jsonl')


class Velocity:
    x = 0.0
    y = 4.0
    z = 0.0


class Actor:
    def __init__(self):
        self.applied = []

    def get_velocity(self):
        return Velocity()

    def apply_control(self, control):
        self.applied.append(control)


def rejected(call):
    try:
        call()
    except ValueError:
        return True
    return False


def main():
    commands = []
    for target in TARGETS_MPS:
        actor = Actor()
        receipt = command_through(actor, target, dict)
        assert actor.applied == [receipt['through_command']]
        assert receipt['through_target_mps'] == target
        commands.append(receipt)
    assert rejected(lambda: command_through(Actor(), 14.0, dict))
    rows = [json.loads(line) for line in SOURCE.read_text().splitlines()]
    samples = body_speed_samples(rows)
    assert len(samples) == len(rows) - 1 == 599
    assert all(sample['actor_id'] == rows[0]['through']['actor_id'] for sample in samples)
    assert rejected(lambda: body_speed_samples([rows[0], {**rows[1], 'time_s': rows[0]['time_s']}]))
    changed = json.loads(json.dumps(rows[1]))
    changed['through']['actor_id'] += 1
    assert rejected(lambda: body_speed_samples([rows[0], changed]))
    fixture_results = []
    for target in TARGETS_MPS:
        fixture = []
        for index in range(5):
            row = json.loads(json.dumps(rows[0]))
            row['frame'] = 100 + index
            row['time_s'] = 5.0 + .05 * index
            for vertex in row['through']['body_vertices_m']:
                vertex[1] -= target * .05 * index
            fixture.append(row)
        measured = body_speed_samples(fixture)
        assert all(abs(item['through_vehicle_speed_mps'] - target) < 1e-10
                   for item in measured)
        fixture_results.append({'target_mps': target, 'measured_mps': median(
            item['through_vehicle_speed_mps'] for item in measured)})
    receipt = {
        'format': 'c158190-through-speed-cpu-construction-proof',
        'source_kind': 'synthetic compatibility body history; not Native capture',
        'source_path': str(SOURCE.relative_to(ROOT.parent.parent)),
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'source_frame_count': len(rows),
        'source_actor_id': rows[0]['through']['actor_id'],
        'source_measured_median_mps': median(
            item['through_vehicle_speed_mps'] for item in samples),
        'declared_targets_mps': list(TARGETS_MPS),
        'controller_commands': commands,
        'fixture_readback': fixture_results,
        'negative_time_and_identity_proofs': True,
        'native_feasibility_proven': False,
        'original_pixels_reviewed': False,
        'legal_hazard_cutoff_claimed': False,
    }
    out = ROOT / 'through-speed-sweep-cpu-proof.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'source_frames': len(rows),
                      'targets_mps': list(TARGETS_MPS)}))


if __name__ == '__main__':
    main()
