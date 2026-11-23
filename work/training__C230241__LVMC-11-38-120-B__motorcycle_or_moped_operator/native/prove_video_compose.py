"""Check the four-source FFV1 composition software path on short media."""
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / '.runtime-work' / 'c230241-video-compose-proof'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr[-1000:])
    return result


def probe(path):
    result = run(['ffprobe', '-v', 'error', '-count_frames',
                  '-select_streams', 'v:0',
                  '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames',
                  '-of', 'json', str(path)])
    return json.loads(result.stdout)['streams'][0]


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    colors = ('red', 'green', 'blue', 'yellow')
    for view, color in zip(VIEWS, colors):
        path = SCRATCH / (view + '.mkv')
        if path.exists():
            path.unlink()
        run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
             '-i', f'color=c={color}:s=64x64:r=20:d=2',
             '-frames:v', '40', '-c:v', 'ffv1', str(path)])
    output = SCRATCH / 'raw.mkv'
    if output.exists():
        output.unlink()
    inputs = [item for view in VIEWS for item in
              ('-i', str(SCRATCH / (view + '.mkv')))]
    layout = ('[0:v]scale=960:540[v0];[1:v]scale=960:540[v1];'
              '[2:v]scale=960:540[v2];[3:v]scale=960:540[v3];'
              '[v0][v1][v2][v3]xstack=inputs=4:'
              'layout=0_0|960_0|0_540|960_540[out]')
    run(['ffmpeg', '-nostdin', '-v', 'error', *inputs,
         '-filter_complex', layout, '-map', '[out]',
         '-frames:v', '40', '-c:v', 'ffv1', str(output)])
    observed = {name: probe(SCRATCH / (name + '.mkv')) for name in VIEWS}
    composed = probe(output)
    assert all(value['nb_read_frames'] == '40' and
               value['avg_frame_rate'] == '20/1' for value in observed.values())
    assert composed['nb_read_frames'] == '40'
    assert composed['avg_frame_rate'] == '20/1'
    assert (composed['width'], composed['height']) == (1920, 1080)
    receipt = {'format': 'c230241-video-compose-software-proof-v1',
               'diagnostic_only': True, 'short_test_frames': 40,
               'full_capture_frames_checked_by_offline': 600,
               'fps': 20, 'input_probes': observed,
               'composed_probe': composed,
               'input_sha256': {name: sha(SCRATCH / (name + '.mkv'))
                                for name in VIEWS},
               'composed_sha256': sha(output),
               'runner_sha256': sha(HERE / 'native_runner.py')}
    path = HERE / 'video-compose-proof.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'receipt_sha256': sha(path)}))


if __name__ == '__main__':
    main()
