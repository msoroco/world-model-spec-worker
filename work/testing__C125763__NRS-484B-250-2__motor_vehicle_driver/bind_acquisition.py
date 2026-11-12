"""Document Native acquisition for every mandatory atom and derived channel."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        construction = json.loads((HERE / entry['construction']).read_text())
        files = {row['path']: row['content'] for row in construction['files']}
        config = json.loads(files['config.json'])
        required = set(config['required_atoms'])
        if not {'ru.subject', 'ru.motor_vehicle', 'kin.position', 'kin.velocity',
                'kin.speed', 'st.intersection', 'rel.bearing'} <= required:
            raise ValueError('Mandatory Native atom inventory differs')
        if 'PipelineCapture(' not in files['runner.py'] or 'capture_helper.capture(' not in files['runner.py']:
            raise ValueError('Native pipeline graph acquisition absent')
        if 'entry_timing.jsonl' not in files['finalizer.py']:
            raise ValueError('Original-frame timing channel absent')
        acquisition = {atom: {
            'entrypoint': 'runner.py',
            'method': 'PipelineCapture.capture at each synchronized Native world tick',
            'evidence': 'Original Native scene graphs and required_observations=config[required_atoms]'
        } for atom in sorted(required)}
        acquisition['entry_timing'] = {
            'entrypoint': 'finalizer.py',
            'method': 'complete-body first entry joined to original Native frame map',
            'evidence': 'crossing_history.jsonl, video_frames.jsonl and junction_context.json'
        }
        entry['acquisition'] = acquisition
        print(entry['case_id'] + ': ' + str(len(acquisition)) + ' acquisition paths bound')
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
