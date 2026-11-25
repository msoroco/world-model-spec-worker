"""Three-frame source-bound diagnostic for an exact saved delivery audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from bicycle_encounter import ASSIGNMENT, CASE_VARIANTS
from delivery_audit import audit
from delivery_decode import finalize_delivery
from original_source_index import build
from saved_attempt import VIEWS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(case, donor, output):
    if case not in {ASSIGNMENT + '__' + suffix for suffix in CASE_VARIANTS}:
        raise ValueError('foreign exact case')
    donor_attempt = Path(donor).resolve()
    donor = donor_attempt / 'capture'
    output = Path(output).resolve()
    repo = Path(__file__).resolve().parents[2]
    if repo / '.runtime-work' not in output.parents or output.exists():
        raise ValueError('new diagnostic output under .runtime-work required')
    output.mkdir(parents=True)
    attempt = output
    output = attempt / 'capture'
    output.mkdir()
    for name in ('config.json', 'candidate-selection.json'):
        shutil.copyfile(donor_attempt / name, attempt / name)
    site = json.loads((donor / 'site.json').read_text())
    if site['case_id'] != case:
        raise ValueError('donor case identity differs')
    for ref in site['original_sources']:
        source = (donor / ref['path']).resolve()
        if not source.is_relative_to(donor) or sha(source) != ref['sha256']:
            raise ValueError('donor original source changed')
        target = output / ref['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(donor / 'site.json', output / 'site.json')
    events = json.loads((donor / 'events.json').read_text())[:3]
    mapping = [json.loads(row) for row in (donor / 'video_frames.jsonl').read_text().splitlines()[:3]]
    if len(events) != 3 or len(mapping) != 3:
        raise ValueError('donor lacks three original frames')
    (output / 'events.json').write_text(json.dumps(events) + '\n')
    (output / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
    from PIL import Image, ImageDraw
    for view in VIEWS:
        directory = output / 'camera-originals' / view
        directory.mkdir(parents=True)
        for number, row in enumerate(events):
            image = Image.new('RGB', (64, 64), (20, 65, 115))
            draw = ImageDraw.Draw(image)
            shift = number
            draw.ellipse((28 + shift, 8, 36 + shift, 16), fill='white')
            draw.line((32 + shift, 16, 32 + shift, 37), fill='white', width=3)
            if site['rider_kind'] == 'electric_scooter':
                draw.line((18 + shift, 46, 47 + shift, 46), fill='white', width=3)
                draw.line((46 + shift, 46, 46 + shift, 28), fill='white', width=2)
            else:
                draw.ellipse((16 + shift, 39, 28 + shift, 51), outline='white', width=2)
                draw.ellipse((38 + shift, 39, 50 + shift, 51), outline='white', width=2)
                draw.line((22 + shift, 45, 33 + shift, 35, 44 + shift, 45),
                          fill='white', width=2)
            image.save(directory / f"{row['frame']:08d}.png")
        command = ['ffmpeg', '-nostdin', '-v', 'error', '-framerate', '20',
                   '-start_number', str(events[0]['frame']), '-i',
                   str(directory / '%08d.png'), '-frames:v', '3', '-c:v',
                   'ffv1', '-pix_fmt', 'bgr0', str(output / (view + '.mkv'))]
        subprocess.run(command, check=True, capture_output=True)
    build(output, case, expected_frames=3)
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'source_index_sha256': sha(output / 'source-index.json')}, indent=2) + '\n')
    refs = {key: {'path': key + '.mkv', 'sha256': sha(output / (key + '.mkv'))}
            for key in VIEWS}
    measurement = finalize_delivery(site, output,
                                    {'path': 'events.json', 'sha256': sha(output / 'events.json')},
                                    refs, CASE_VARIANTS[case.removeprefix(ASSIGNMENT + '__')]['mode'], 3)
    index = json.loads((output / 'source-index.json').read_text())
    review = {'case_id': case, 'source_index_sha256': sha(output / 'source-index.json'),
              'site_sha256': sha(output / 'site.json'),
              'events_sha256': sha(output / 'events.json'),
              'views': {}, 'physical_review': {'completed': True,
              'first_frame': events[0]['frame'], 'last_frame': events[-1]['frame'],
              'reviewer': 'synthetic-fixture-review'},
              'lawful_riding_verdict': None, 'intent_verdict': None,
              'interference_verdict': None}
    for view in VIEWS:
        review['views'][view] = {
            'video_sha256': refs[view]['sha256'],
            'framemd5_sha256': measurement['camera_decode_receipts'][view]['framemd5_sha256'],
            'samples': [{'frame': 1, 'rider_visible': True,
                         'rider_kind': site['rider_kind'],
                         'original_png_sha256': index['camera_originals'][view][1]['image']['sha256'],
                         'reviewer': 'synthetic-fixture-review'}]}
    return review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--donor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('positive', 'negative',
                                           'negative_native', 'negative_seal',
                                           'negative_source'), required=True)
    args = parser.parse_args()
    review = prepare(args.case, args.donor, args.output)
    if args.mode == 'negative':
        review['views']['approach']['framemd5_sha256'] = '0' * 64
    if args.mode in ('negative_seal', 'negative_source'):
        (args.output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'source_index_sha256': sha(args.output / 'capture' / 'source-index.json')},
            indent=2) + '\n')
        (args.output / 'capture-seal.json').write_text(json.dumps({
            'format': 'worker-sealed-capture', 'provenance_kind': 'native',
            'diagnostic_fixture': False, 'frames': 3,
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'restoration': {'restored': True},
            'encoder_exit_codes': {view: 0 for view in VIEWS},
            'sources': {'capture/source-index.json': '0' * 64},
            'source_digest': '0' * 64,
            'native_revision': {}}, indent=2) + '\n')
        (args.output / 'acquisition-context.json').write_text(json.dumps({
            'case_id': args.case,
            'source_index_sha256': sha(args.output / 'capture' / 'source-index.json')},
            indent=2) + '\n')
    path = args.output / 'pixel-review.json'
    path.write_text(json.dumps(review, indent=2) + '\n')
    if args.mode == 'negative_source':
        from worker_exchange.common import digest, tree
        (args.output / 'capture-seal.json').unlink()
        (args.output / 'runner.py').write_text('# forged diagnostic runner\n')
        (args.output / 'construction.json').write_text('{"diagnostic": true}\n')
        for name in ('trace.jsonl', 'video_frames.jsonl'):
            source = args.output / 'capture' / name
            if source.is_file():
                shutil.copyfile(source, args.output / name)
        if not (args.output / 'trace.jsonl').exists():
            (args.output / 'trace.jsonl').write_text('{"diagnostic": true}\n')
        for view in VIEWS:
            shutil.copyfile(args.output / 'capture' / (view + '.mkv'),
                            args.output / (view + '.mkv'))
        sources = tree(args.output)
        sources['capture/events.json'] = '0' * 64
        (args.output / 'capture-seal.json').write_text(json.dumps({
            'format': 'worker-sealed-capture', 'provenance_kind': 'native',
            'diagnostic_fixture': False, 'frames': 3,
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'restoration': {'restored': True},
            'encoder_exit_codes': {view: 0 for view in VIEWS},
            'sources': sources, 'source_digest': digest(sources),
            'native_revision': {'construction_sha256': sources['construction.json'],
                                'runner_sha256': sources['runner.py']}}, indent=2) + '\n')
    result = audit(args.output, args.case, path, expected_frames=3,
                   diagnostic_fixture=args.mode in ('positive', 'negative'))
    print(json.dumps({'scope': 'synthetic source and pixel diagnostic only',
                      'result': result}, indent=2))


if __name__ == '__main__':
    main()
