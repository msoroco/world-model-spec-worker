"""Append original Native directed-roadway samples with exact frame joins."""

import json
from pathlib import Path

from directed_geometry import adjacent_opposing_lane, footprint_row


class RoadwaySourceRecorder:
    def __init__(self, directory, ego):
        self.ego = ego
        self.path = Path(directory) / 'directed_roadway_footprints.jsonl'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise ValueError('Original roadway source already exists')
        self.file = self.path.open('x', encoding='utf-8')
        self.previous = None

    def append(self, frame, time_s, subject_waypoint):
        if self.file.closed:
            raise ValueError('Original roadway source is closed')
        if self.previous is not None:
            old_frame, old_time = self.previous
            if frame != old_frame + 1 or abs(time_s - old_time - .05) > 1e-4:
                raise ValueError('Native roadway sample did not advance at 20 Hz')
        opposite = adjacent_opposing_lane(subject_waypoint)
        row = footprint_row(self.ego, subject_waypoint, opposite, frame, time_s)
        self.file.write(json.dumps(row, sort_keys=True) + '\n')
        self.file.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.file.close()
