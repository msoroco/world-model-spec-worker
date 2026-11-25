"""Build the distinct 30-second lateral-duration fallback without altering drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def main():
    for witness in ('witness_1', 'witness_2'):
        base = json.loads((HERE / 'extended-primary' / witness / 'construction.json').read_text())
        files = {item['path']: item for item in base['files']}
        config = json.loads(files['config.json']['content'])
        fallback = json.loads((HERE / 'native/drafts' / witness / 'fallback2/config.json').read_text())
        assert config['policy']['camera_fov_deg'] == fallback['policy']['camera_fov_deg'] == 85
        assert fallback['policy']['lateral_duration_frames'] == 55
        config['candidate_id'] = 'fallback2'
        config['policy'] = fallback['policy']
        rows = []
        for frame in range(600):
            x = round(10 + 4 * frame / 20, 4)
            if witness == 'witness_1':
                y = -1.75
            else:
                fraction = max(0, min(1, (frame - config['policy']['lateral_start_frame']) /
                                       config['policy']['lateral_duration_frames']))
                y = round(-1.75 - 2.75 * fraction, 4)
            rows.append({'frame': frame, 'time_s': round(frame / 20, 4),
                         'motorcycle_blueprint': 'vehicle.kawasaki.ninja',
                         'requested_center_xy_m': [x, y], 'requested_speed_mps': 4.0,
                         'requested_body_width_m': .8,
                         'source_kind': 'authored_native_request'})
        tracks = b''.join(json.dumps(row, sort_keys=True).encode() + b'\n' for row in rows)
        config['tracks_sha256'] = sha(tracks)
        files['requested-tracks.jsonl']['content'] = tracks.decode()
        files['config.json']['content'] = encoded(config).decode()
        path = HERE / 'extended-primary' / witness / 'fallback2/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded(base))
        overlap = sum(row['requested_center_xy_m'][1] - .4 < -3.5 and
                      row['requested_center_xy_m'][1] + .4 > -5.5 for row in rows)
        assert overlap == (0 if witness == 'witness_1' else 512)
        print(json.dumps({'witness': witness, 'candidate': 'fallback2',
                          'construction_sha256': sha(path.read_bytes()),
                          'requested_overlap_frames': overlap}))


if __name__ == '__main__':
    main()
