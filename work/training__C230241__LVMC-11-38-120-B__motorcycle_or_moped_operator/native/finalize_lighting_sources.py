"""Finalize one source-bound 600-frame lighting review without a legal verdict."""
import argparse
import json
from pathlib import Path

from bind_lighting_sources import bind, sha
from join_lighting_review import join
from measure_lighting import measure


def finalize(source_dir, measurement_context, output_dir):
    source_dir = Path(source_dir)
    measurement_context = Path(measurement_context)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError('Choose a new output directory to preserve prior proof')
    binding = bind(source_dir, 600)
    measurement_setup = json.loads(measurement_context.read_text())
    expected_kind = ('synthetic_native_sample' if binding['diagnostic_only']
                     else 'calibrated_original_review')
    if measurement_setup.get('source_kind') != expected_kind:
        raise ValueError('Measurement context source kind differs from bound sources')
    output_dir.mkdir(parents=True)
    joined_path = output_dir / 'joined-lighting.jsonl'
    joined = join(source_dir / 'native-lighting-frames.jsonl',
                  source_dir / 'lighting-review.jsonl',
                  source_dir / 'video_frames.jsonl', joined_path)
    if joined['native_source_sha256'] != binding['source_sha256']['native-lighting-frames.jsonl']:
        raise ValueError('Native source changed between binding and join')
    if joined['frame_map_sha256'] != binding['source_sha256']['video_frames.jsonl']:
        raise ValueError('Frame map changed between binding and join')
    if joined['review_source_sha256'] != binding['review_sha256']:
        raise ValueError('Review changed between binding and join')
    measured = measure(joined_path, measurement_context,
                       source_dir / 'video_frames.jsonl')
    if measured['source_sha256'] != joined['joined_sha256']:
        raise ValueError('Joined measurements changed before finalization')
    if measured['frame_map_sha256'] != joined['frame_map_sha256']:
        raise ValueError('Frame map changed before finalization')
    receipt = {'format': 'c230241-saved-lighting-finalization-v1',
               'binding': binding, 'join': joined, 'measurement': measured,
               'measurement_context_sha256': sha(measurement_context),
               'source_dir': str(source_dir),
               'joined_output_sha256': sha(joined_path),
               'diagnostic_only': bool(json.loads(
                   (source_dir / 'lighting-review-context.json').read_text()
               ).get('diagnostic_only', False)),
               'original_native_verified': False,
               'physical_visibility_verified': False,
               'legal_verdict_claimed': False}
    receipt_path = output_dir / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--measurement-context', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    receipt_path = finalize(args.source_dir, args.measurement_context,
                            args.output_dir)
    print(json.dumps({'receipt': str(receipt_path),
                      'receipt_sha256': sha(receipt_path)}))


if __name__ == '__main__':
    main()
