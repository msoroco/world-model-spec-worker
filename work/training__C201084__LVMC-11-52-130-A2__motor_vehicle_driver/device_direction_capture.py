"""Add a frame-synchronized original light readback to the Native stop probe."""
import json
from pathlib import Path

from device_direction_probe import check_saved_device_rows, sample_device
from fire_lane_survey import require
from native_capture import OriginalFrameMap, acquire_with_world_restore


class DeviceFrameMap(OriginalFrameMap):
    def __init__(self, path, device, readback):
        super().__init__(path)
        self.device = device
        self.readback = readback
        self.device_path = Path(path).with_name('traffic-control-device.jsonl')
        self.device_stream = self.device_path.open('x', encoding='utf-8')

    def append(self, frame, time_s):
        mapped = super().append(frame, time_s)
        source = sample_device(self.device, self.readback, frame)
        source['video_frame'] = mapped['video_frame']
        self.device_stream.write(json.dumps(source, allow_nan=False)+'\n')
        return mapped

    def close(self):
        try:
            self.device_stream.close()
        finally:
            super().close()


def acquire(world, carla, ego, follower, sign, device, plan, attempt,
            *, base_acquire=acquire_with_world_restore):
    require(plan['capture_hz'] == 20 and plan['capture_frames'] >= 600 and
            len(plan['camera_names']) == 4,
            'Device probe must retain full four-camera capture')
    readback = plan['traffic_control_device_readback']
    attempt = Path(attempt)
    require(not (attempt/'traffic-control-device.jsonl').exists(),
            'Retain original device source; use fresh attempt')
    result = base_acquire(
        world, carla, ego, follower, sign, plan, 'reference', attempt,
        frame_map_factory=lambda path: DeviceFrameMap(path,device,readback))
    with (attempt/'traffic-control-device.jsonl').open() as stream:
        device_rows = [json.loads(line) for line in stream]
    with (attempt/'video_frames.jsonl').open() as stream:
        frame_rows = [{'frame':json.loads(line)['carla_frame']}
                      for line in stream]
    measured = check_saved_device_rows(device_rows,frame_rows,readback)
    result['device_source'] = 'traffic-control-device.jsonl'
    result['device_measurement'] = measured
    result['direction_applicability_verified'] = False
    result['statutory_necessity_verified'] = False
    return result
