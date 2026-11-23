"""Frame-synchronized original pedestrian readback for a draft officer probe."""
import json
from pathlib import Path

from fire_lane_survey import require
from native_capture import OriginalFrameMap, acquire_with_world_restore
from officer_direction_probe import check_saved_officer_rows, sample_officer


class OfficerFrameMap(OriginalFrameMap):
    def __init__(self, path, actor, readback):
        super().__init__(path)
        self.actor = actor
        self.readback = readback
        self.officer_path = Path(path).with_name('police-officer-actor.jsonl')
        self.officer_stream = self.officer_path.open('x', encoding='utf-8')

    def append(self, frame, time_s):
        mapped = super().append(frame, time_s)
        row = sample_officer(self.actor, self.readback, frame)
        row['video_frame'] = mapped['video_frame']
        self.officer_stream.write(json.dumps(row, allow_nan=False) + '\n')
        return mapped

    def close(self):
        try:
            self.officer_stream.close()
        finally:
            super().close()


def acquire(world, carla, ego, follower, sign, officer, plan, attempt,
            *, base_acquire=acquire_with_world_restore):
    require(plan['capture_hz'] == 20 and plan['capture_frames'] >= 600 and
            len(plan['camera_names']) == 4,
            'Officer probe must retain full four-camera capture')
    attempt = Path(attempt)
    require(not (attempt/'police-officer-actor.jsonl').exists(),
            'Retain original officer source; use fresh attempt')
    readback = plan['police_officer_readback']
    result = base_acquire(
        world, carla, ego, follower, sign, plan, 'reference', attempt,
        frame_map_factory=lambda path: OfficerFrameMap(path, officer, readback))
    with (attempt/'police-officer-actor.jsonl').open() as stream:
        rows = [json.loads(line) for line in stream]
    with (attempt/'video_frames.jsonl').open() as stream:
        frames = [{'frame': json.loads(line)['carla_frame']} for line in stream]
    result['officer_source'] = 'police-officer-actor.jsonl'
    result['officer_measurement'] = check_saved_officer_rows(rows, frames, readback)
    return result
