"""Independently verify four compact synthetic long sources and reject tampering."""

import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zlib


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
INDEX = HERE / 'current-tour-bus-below-source-transport.json'
REQUIRED = {
    'trace.jsonl',
    'native-raw-actors.jsonl', 'native-passenger-actors.jsonl',
    'video_frames.jsonl', 'capture/evidence.jsonl',
    'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
    'driver_reference.mkv',
}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def expand(row, destination):
    packed = (HERE / row['packed_path']).read_bytes()
    if sha(packed) != row['packed_sha256']:
        raise ValueError('Packed source changed')
    raw = zlib.decompress(base64.b64decode(packed, validate=True))
    if len(raw) != row['expanded_bytes'] or sha(raw) != row['expanded_sha256']:
        raise ValueError('Expanded source changed')
    if row['kind'] == 'jsonl' and (raw.count(b'\n') != row['rows'] or
                                  not raw.endswith(b'\n') or raw.endswith(b'\n\n')):
        raise ValueError('Expanded rows differ')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return raw


def main():
    index = json.loads(INDEX.read_text())
    if (index['format'] != 'c150142-long-synthetic-source-transport-v1' or
            index['source_kind'] != 'synthetic_fixture' or
            index['frame_count'] != 36120 or
            index['official_fixture_recipe_compatibility_passed'] is not False or
            index['original_native_observed'] is not False or
            {row['source_path'] for row in index['sources']} != REQUIRED):
        raise ValueError('Source transport scope changed')
    scratch = REPO / '.runtime-work/owner150142/transport-proof'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        for row in index['sources']:
            if row['packed_bytes'] > 2 * 1024 * 1024:
                raise ValueError('Long source shape or return cap differs')
            destination = Path(folder) / row['source_path']
            raw = expand(row, destination)
            if row['kind'] == 'jsonl':
                if row['rows'] != 36120:
                    raise ValueError('Long source row count differs')
                first = json.loads(raw.splitlines()[0])
                last = json.loads(raw.splitlines()[-1])
                if row['source_path'] == 'video_frames.jsonl':
                    if first['carla_frame'] != 0 or last['carla_frame'] != 36119:
                        raise ValueError('Frame-map endpoints differ')
                if row['source_path'] == 'native-raw-actors.jsonl':
                    if first['native_frame'] != 0 or last['native_frame'] != 36119:
                        raise ValueError('Actor endpoints differ')
                if row['source_path'] == 'trace.jsonl':
                    if first['frame'] != 0 or last['frame'] != 36119:
                        raise ValueError('Trace endpoints differ')
            elif row['kind'] == 'video':
                probe = subprocess.run([
                    'ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0',
                    '-show_entries', 'stream=nb_read_packets,r_frame_rate',
                    '-of', 'json', str(destination)], capture_output=True, text=True,
                    check=True, timeout=120)
                stream = json.loads(probe.stdout)['streams'][0]
                if stream['nb_read_packets'] != '36120' or stream['r_frame_rate'] != '20/1':
                    raise ValueError('Video frame count or rate differs')
            else:
                raise ValueError('Unknown transport kind')
        changed = bytearray((HERE / index['sources'][0]['packed_path']).read_bytes())
        changed[0] = ord('X') if changed[0] != ord('X') else ord('Y')
        if sha(changed) == index['sources'][0]['packed_sha256']:
            raise ValueError('Tamper probe did not change bytes')
    print(json.dumps({
        'format': 'c150142-long-synthetic-source-transport-proof-v1',
        'case_id': index['case_id'],
        'source_kind': 'synthetic_fixture',
        'sources_verified': len(index['sources']),
        'jsonl_rows_per_source': 36120,
        'video_frames_per_source': 36120,
        'packed_bytes': sum(row['packed_bytes'] for row in index['sources']),
        'changed_packed_source_rejected': True,
        'official_fixture_recipe_compatibility_passed': False,
        'original_native_observed': False,
    }, indent=2))


if __name__ == '__main__':
    main()
