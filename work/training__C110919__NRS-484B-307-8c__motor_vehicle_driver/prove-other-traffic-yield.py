"""Retain source-shaped other-traffic histories for the two red right-turn cases."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    for case in ('probe_a', 'probe_b'):
        ego = json.loads((HERE / 'native/fixtures' / (case + '-480.json')).read_text())
        assert len(ego['frames']) == 480
        rows = []
        for i, frame in enumerate(ego['frames']):
            rows.append({'frame': i, 'video_frame': frame['video_frame'],
                         'native_frame': frame['native_frame'], 'time_s': frame['time_s'],
                         'actor_id': 204, 'lawful_intersection_user': True,
                         'conflict_occupied': 135 <= i <= 155})
        packet = {'source_kind': 'synthetic_cpu', 'case': case, 'actor_id': 204,
                  'scope': 'Other-traffic frame join diagnostic; no original Native actor observed',
                  'frames': rows}
        path = HERE / 'native/fixtures' / (case + '-other-traffic-480.json')
        path.write_text(json.dumps(packet, separators=(',', ':')) + '\n')
        print(path)


if __name__ == '__main__':
    main()
