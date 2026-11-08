"""Exercise the proposed Native controller in a small deterministic bicycle model.

This is a CPU model of steering response, not a CARLA motorcycle observation.
"""
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

from runner import _control

HERE = Path(__file__).resolve().parent
CASES = ('witness_1', 'witness_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
DT = .05
WHEELBASE_M = 1.4
MAX_STEER_DEG = 35.0
BODY_LENGTH_M = 2.2
BODY_WIDTH_M = .8


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Actor:
    def __init__(self):
        self.x, self.y, self.yaw, self.speed = 10.0, 1.75, 0.0, 0.0

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=self.y),
                               rotation=SimpleNamespace(yaw=math.degrees(self.yaw)))

    def get_velocity(self):
        return SimpleNamespace(x=self.speed*math.cos(self.yaw),
                               y=self.speed*math.sin(self.yaw), z=0.0)

    def tick(self, command):
        acceleration = 3.0*command.throttle - 5.0*command.brake - .05*self.speed
        self.speed = max(0.0, self.speed + acceleration*DT)
        steer_angle = command.steer*math.radians(MAX_STEER_DEG)
        self.yaw += self.speed/WHEELBASE_M*math.tan(steer_angle)*DT
        self.x += self.speed*math.cos(self.yaw)*DT
        self.y += self.speed*math.sin(self.yaw)*DT


class CarlaStub:
    @staticmethod
    def VehicleControl(**values):
        return SimpleNamespace(**values)


def body(actor):
    return [[round(actor.x + dx*math.cos(actor.yaw) - dy*math.sin(actor.yaw), 5),
             round(actor.y + dx*math.sin(actor.yaw) + dy*math.cos(actor.yaw), 5)]
            for dx, dy in ((-BODY_LENGTH_M/2, -BODY_WIDTH_M/2),
                           (-BODY_LENGTH_M/2, BODY_WIDTH_M/2),
                           (BODY_LENGTH_M/2, -BODY_WIDTH_M/2),
                           (BODY_LENGTH_M/2, BODY_WIDTH_M/2))]


def simulate(folder):
    requests = [json.loads(line) for line in (folder / 'requested-tracks.jsonl').read_text().splitlines()]
    actor = Actor()
    rows = []
    for index in range(480):
        point = requests[min(479, index+15)]['requested_center_xy_m']
        target = (point[0], -point[1])
        command, control = _control(CarlaStub, actor, target, WHEELBASE_M, MAX_STEER_DEG)
        actor.tick(command)
        polygon = body(actor)
        ys = [point[1] for point in polygon]
        requested = requests[index]['requested_center_xy_m']
        rows.append({'frame': index, 'time_s': round(index*DT, 4),
                     'center_native_xy_m': [round(actor.x, 5), round(actor.y, 5)],
                     'body_native_xy_m': polygon,
                     'speed_mps': round(actor.speed, 5),
                     'heading_deg': round(math.degrees(actor.yaw), 5),
                     'requested_native_xy_m': [requested[0], -requested[1]],
                     'target_native_xy_m': list(target),
                     'throttle': round(control['throttle'], 8),
                     'brake': round(control['brake'], 8),
                     'steer': round(control['steer'], 8),
                     'moving_sidewalk_overlap': actor.speed > .1 and min(ys) < 5.5 and max(ys) > 3.5})
    return rows


def main():
    receipts = []
    for case in CASES:
        for candidate in CANDIDATES:
            folder = HERE / 'drafts' / case / candidate
            config = json.loads((folder / 'config.json').read_text())
            if (config['case_suffix'] != case or config['candidate_id'] != candidate or
                    config['road_sha256'] != sha(HERE / 'road.xodr') or
                    config['tracks_sha256'] != sha(folder / 'requested-tracks.jsonl') or
                    config['case_plan_sha256'] != sha(HERE.parent / 'case-plan.json')):
                raise AssertionError('Controller model request source differs')
            rows = simulate(folder)
            overlaps = [row['frame'] for row in rows if row['moving_sidewalk_overlap']]
            end = rows[-1]
            cross_track = [abs(row['center_native_xy_m'][1] - row['requested_native_xy_m'][1])
                           for row in rows[160:]]
            metric = {'case_suffix': case, 'candidate_id': candidate,
                      'first_moving_sidewalk_overlap_frame': overlaps[0] if overlaps else None,
                      'moving_sidewalk_overlap_frames': len(overlaps),
                      'terminal_x_m': end['center_native_xy_m'][0],
                      'terminal_y_m': end['center_native_xy_m'][1],
                      'terminal_speed_mps': end['speed_mps'],
                      'max_lateral_error_after_frame_160_m': round(max(cross_track), 5)}
            if case == 'witness_1' and overlaps:
                raise AssertionError('CPU controller model entered sidewalk in roadway witness')
            if case == 'witness_2' and len(overlaps) < 375:
                raise AssertionError('CPU controller model failed sidewalk occupancy window')
            if end['center_native_xy_m'][0] < 100 or max(cross_track) > .4:
                raise AssertionError('CPU controller model failed terminal tracking bound')
            output = HERE / 'controller-fixtures' / case / (candidate + '.jsonl')
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
            receipts.append({**metric, 'request_sha256': sha(folder / 'requested-tracks.jsonl'),
                             'config_sha256': sha(folder / 'config.json'),
                             'trajectory_sha256': sha(output)})
    by_case = {(r['case_suffix'], r['candidate_id']): r for r in receipts}
    primary = by_case['witness_2', 'primary']['first_moving_sidewalk_overlap_frame']
    early = by_case['witness_2', 'fallback1']['first_moving_sidewalk_overlap_frame']
    slow = by_case['witness_2', 'fallback2']['first_moving_sidewalk_overlap_frame']
    if not early < primary < slow:
        raise AssertionError('CPU controller model did not preserve fallback timing order')
    proof = {'format': 'c422978-cpu-controller-model-proof-v1',
             'model': {'dt_s': DT, 'wheelbase_m': WHEELBASE_M,
                       'max_steer_deg': MAX_STEER_DEG,
                       'body_length_m': BODY_LENGTH_M, 'body_width_m': BODY_WIDTH_M,
                       'acceleration': '3*throttle - 5*brake - .05*speed'},
             'runner_sha256': sha(HERE / 'runner.py'),
             'draft_manifest_sha256': sha(HERE / 'drafts/manifest.json'),
             'receipts': receipts, 'original_native_observed': False,
             'carla_run': False, 'delivery_ready': False}
    (HERE / 'controller-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'models': len(receipts), 'early_primary_slow': [early, primary, slow]}))


if __name__ == '__main__':
    main()
