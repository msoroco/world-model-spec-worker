"""Bind every selected recording channel to its case acquisition code and files."""
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
MANIFEST = FOLDER / 'execution-manifest.json'


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        construction = json.loads((FOLDER / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        acquisition = entry.setdefault('acquisition', {})
        for channel in config['recording_description']['channels']:
            name = channel['name']
            derived = name in ('edge_parallel_angle_deg', 'lawful_traffic_heading_angle_deg')
            acquisition[name] = {'entrypoint': 'finalize.py' if derived else 'capture.py',
                'method': 'saved original Native pose and roadway geometry projection' if derived
                          else 'same-tick Native readback with saved source context',
                'evidence': 'native_samples.jsonl, video_frames.jsonl, body_history.jsonl, '
                            'road_geometry.json, road_edge_survey.json, activity_context.json'}
        for atom in config['required_atoms']:
            acquisition.setdefault(atom, {'entrypoint': 'capture.py',
                'method': 'same-tick original Native readback',
                'evidence': 'capture/evidence.jsonl and trace.jsonl'})
    MANIFEST.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
