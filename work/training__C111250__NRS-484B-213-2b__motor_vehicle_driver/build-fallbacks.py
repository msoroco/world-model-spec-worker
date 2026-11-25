"""Predeclare lower requested speed when original Native lane tracking fails."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = FOLDER / 'selected-probe-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((FOLDER / entry['construction']).read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        if config['requested_speed_mps'] != 3.4:
            raise ValueError('Unexpected primary request')
        config['requested_speed_mps'] = 2.8
        config['candidate_id'] = 'fallback1'
        files['config.json'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
        construction['files'] = [{'path': name, 'content': content} for name, content in files.items()]
        construction['candidate_id'] = 'fallback1'
        construction['measurement_plan']['fallback_note'] = ('2.8 m/s requested speed retains the exact road and observations; '
            'the CPU fixture tests software compatibility only and does not demonstrate this Native fallback trajectory')
        dest = FOLDER / 'selected-candidates' / suffix / 'fallback1' / 'construction.json'
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(construction, indent=2, ensure_ascii=False) + '\n')
        entry['candidates'] = [{'id': 'fallback1', 'construction': dest.relative_to(FOLDER).as_posix(),
                                'construction_sha256': sha(dest),
                                'trigger': {'source': 'original Native body footprint, map lane and frame joins',
                                            'metric': 'actual lateral tracking and full-body centerline occupancy at the approach/traversal zone',
                                            'failure_condition': '3.4 m/s primary departs intended lane, misses the temporal interval or loses frame joins'},
                                'changed_knobs': ['requested speed 3.4 m/s to 2.8 m/s; exact road, case and four-camera capture retained']}]
        print(suffix, sha(dest))
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
