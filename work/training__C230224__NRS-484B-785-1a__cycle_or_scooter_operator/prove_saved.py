"""Exercise original-source joins with locally synthesized diagnostic media."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from measure_scooter import measure, sha
from prove_scooter import fixture


def main():
    with tempfile.TemporaryDirectory(prefix='scooter-saved-', dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp) / 'source'
        fixture(root, 12*.44704, 'controlled_1')
        context_path = root / 'scooter_context.json'
        context = json.loads(context_path.read_text())
        context['review_kind'] = 'original_source_review'
        lines = (root / 'native_rider_trace.jsonl').read_text().splitlines()
        rows = [dict(json.loads(line), source_kind='original_native_pose') for line in lines]
        (root / 'native_rider_trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        hashes = {}
        for name in ('forward', 'rear', 'left', 'right'):
            path = root / ('camera_'+name+'.mkv')
            run = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=16x16:r=20',
                                  '-frames:v', '600', '-c:v', 'ffv1', str(path)], capture_output=True, text=True)
            if run.returncode:
                raise AssertionError('Synthetic saved camera creation failed: '+run.stderr[-500:])
            hashes[path.name] = sha(path)
        context['camera_sha256'] = hashes
        context_path.write_text(json.dumps(context)+'\n')
        out = measure(root)
        assert out['samples'] == 600 and len(out['source_sha256']) == 7
        context['camera_sha256']['camera_left.mkv'] = '0'*64
        context_path.write_text(json.dumps(context)+'\n')
        try:
            measure(root)
        except ValueError:
            pass
        else:
            raise AssertionError('Altered camera provenance accepted')
        print(json.dumps({'saved_join_samples': out['samples'], 'camera_sha256_count': 4,
                          'tamper_rejected': True, 'legal_result': None}, sort_keys=True))


if __name__ == '__main__':
    main()
