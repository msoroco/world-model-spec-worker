"""Build explicit synthetic original-PNG archives for CPU comparison audits."""
import argparse
import hashlib
import io
import json
import pathlib
import shutil
import zipfile

from PIL import Image

from saved_delivery import CAMERAS


def materialize(source, destination):
    source, destination = pathlib.Path(source), pathlib.Path(destination)
    if '.runtime-work' not in destination.resolve().parts or destination.exists():
        raise ValueError('new .runtime-work fixture destination required')
    shutil.copytree(source, destination)
    acquisition_path = destination / 'acquisition.json'
    acquisition = json.loads(acquisition_path.read_text())
    if acquisition.get('diagnostic_fixture') is not True:
        raise ValueError('only diagnostic sources may be transformed')
    frames = [json.loads(line) for line in (destination / 'video_frames.jsonl').read_text().splitlines()]
    if len(frames) != 900:
        raise ValueError('diagnostic fixture must cover exact 45 s')
    media = {}
    for camera_index, name in enumerate(sorted(CAMERAS)):
        archive_path = destination / (name + '.zip')
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as archive:
            for index, frame in enumerate(frames):
                image = Image.new('RGB', (16, 16),
                                  ((index + camera_index) % 256, (index // 3) % 256, camera_index * 35))
                stream = io.BytesIO()
                image.save(stream, format='PNG')
                archive.writestr(f'{index:04d}-{frame["frame"]}.png', stream.getvalue())
        media[name] = {'kind': 'original_native', 'path': archive_path.name,
                       'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest()}
    acquisition['media'] = media
    acquisition_path.write_text(json.dumps(acquisition, indent=2, sort_keys=True) + '\n')
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = materialize(args.source, args.output)
    print(json.dumps({'fixture': str(result), 'diagnostic_only': True,
                      'camera_archives': 4, 'frames_per_camera': 900}, sort_keys=True))


if __name__ == '__main__':
    main()
