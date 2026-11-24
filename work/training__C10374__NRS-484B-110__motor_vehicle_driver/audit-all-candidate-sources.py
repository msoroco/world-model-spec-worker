"""Independently verify current eight route fixtures and four decoded camera streams."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ZONE = HERE / 'native' / 'zone'
CAMERAS = ('forward', 'overview', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_video(path):
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                          '-select_streams', 'v:0', '-show_entries',
                          'stream=codec_name,nb_read_frames', '-of', 'json',
                          str(path)], check=True, capture_output=True, text=True)
    streams = json.loads(run.stdout)['streams']
    if len(streams) != 1 or streams[0]['codec_name'] != 'ffv1' or streams[0]['nb_read_frames'] != '600':
        raise ValueError(f'camera decode contract failed: {path}')
    return sha(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--runtime-work', type=Path, required=True)
    args = p.parse_args()
    base = args.runtime_work.resolve()
    if not base.is_relative_to((ROOT / '.runtime-work').resolve()):
        raise ValueError('scratch must be under .runtime-work')
    records = []
    for condition in ('a', 'b'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            raw = ((ROOT / f'.runtime-work/c10374-current-graph-{condition}') if candidate == 'primary'
                   else base / f'condition_{condition}-{candidate}-raw')
            saved = ((ROOT / f'.runtime-work/c10374-current-saved-{condition}') if candidate == 'primary'
                     else base / f'condition_{condition}-{candidate}-saved')
            suffix = f'selected_c5852cfd__condition_{condition}'
            bundle = ZONE / 'offline/bundles' / suffix / candidate
            receipt = json.loads((saved / 'preparation-receipt.json').read_text())
            if receipt['source_kind'] != 'synthetic_cpu' or receipt['original_native_observed']:
                raise ValueError('diagnostic source mislabeled')
            if receipt['config_sha256'] != sha(bundle / 'config.json'):
                raise ValueError('candidate config changed')
            for name, value in receipt['raw_hashes'].items():
                if sha(raw / name) != value:
                    raise ValueError(f'raw source changed: {name}')
            for name, value in receipt['saved_hashes'].items():
                if sha(saved / name) != value:
                    raise ValueError(f'saved source changed: {name}')
            frame_map = (raw / 'capture/native/frames.jsonl').read_text().splitlines()
            graphs = list((raw / 'capture/native/graphs/base').glob('*.adapter.json'))
            if len(frame_map) != 600 or len(graphs) != 600:
                raise ValueError('graph frame count changed')
            videos = {name: check_video(raw / (name + '.mkv')) for name in CAMERAS}
            records.append({'condition': condition, 'candidate': candidate,
                            'source_graphs': len(graphs), 'frame_map_rows': len(frame_map),
                            'ffv1_cameras': len(videos), 'camera_sha256': videos,
                            'preparation_receipt_sha256': sha(saved / 'preparation-receipt.json')})
    report = {'format': 'c10374-eight-candidate-source-audit-v1', 'passed': True,
              'records': records, 'synthetic_source_only': True,
              'physical_acceptance_claimed': False, 'legal_outcome_claimed': False}
    output = HERE / 'current-graph-fixture/eight-candidate-source-audit.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'candidates': len(records), 'audit_sha256': sha(output)}))


if __name__ == '__main__':
    main()
