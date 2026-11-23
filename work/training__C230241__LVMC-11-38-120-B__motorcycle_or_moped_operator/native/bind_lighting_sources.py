"""Check that an independent lamp review names the exact decoded Native sources.

This is a source-integrity check, not a judgement that the review is calibrated
or that its lamp/range observations are correct.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def probe(path):
    process = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name,avg_frame_rate,nb_read_frames',
         '-of', 'json', str(path)], capture_output=True, text=True, timeout=180)
    require(process.returncode == 0, 'Source video decode failed: ' + str(path))
    streams = json.loads(process.stdout).get('streams', [])
    require(len(streams) == 1, 'Expected one source video stream: ' + str(path))
    return streams[0]


def bind(directory, expected_frames=600):
    directory = Path(directory)
    files = {view: directory / (view + '.mkv') for view in VIEWS}
    trace = directory / 'native-lighting-frames.jsonl'
    frame_map = directory / 'video_frames.jsonl'
    review = directory / 'lighting-review.jsonl'
    context = directory / 'lighting-review-context.json'
    require(all(path.is_file() for path in (*files.values(), trace, frame_map,
                                           review, context)),
            'Original video, trace, frame map or independent review missing')
    facts = json.loads(context.read_text())
    diagnostic = facts.get('diagnostic_only') is True
    expected_review_kind = ('synthetic_native_sample' if diagnostic
                            else 'calibrated_original_review')
    expected_motion_kind = ('synthetic_native_sample' if diagnostic
                            else 'original_native_observation')
    require(facts.get('source_kind') == expected_review_kind,
            'Review context source kind differs from diagnostic/original mode')
    actual_hashes = {view: sha(path) for view, path in files.items()}
    actual_hashes['native-lighting-frames.jsonl'] = sha(trace)
    actual_hashes['video_frames.jsonl'] = sha(frame_map)
    require(facts.get('source_sha256') == actual_hashes,
            'Review source hashes differ from original capture')
    media = {view: probe(path) for view, path in files.items()}
    require(all(item.get('codec_name') == 'ffv1' and
                item.get('avg_frame_rate') == '20/1' and
                item.get('nb_read_frames') == str(expected_frames)
                for item in media.values()),
            'Original source video count, rate or codec differs')
    native, mapping, observed = rows(trace), rows(frame_map), rows(review)
    require(len(native) == len(mapping) == len(observed) == expected_frames,
            'Trace, map and review frame counts differ')
    for index, (motion, identity, evidence) in enumerate(zip(native, mapping, observed)):
        require(all(row.get('video_frame') == index for row in
                    (motion, identity, evidence)) and
                motion.get('native_frame') == identity.get('native_frame') ==
                identity.get('carla_frame') == evidence.get('native_frame') and
                all(abs(row.get('time_s', -999) - index / 20) < 1e-6 for row in
                    (motion, identity, evidence)),
                'Review frame identity differs at ' + str(index))
        require(motion.get('source_kind') == expected_motion_kind and
                'light_state_observed' in motion and
                evidence.get('source_kind') == expected_review_kind,
                'Light-state trace or review source kind differs at ' + str(index))
    return {'format': 'c230241-original-video-review-binding-v1',
            'source_sha256': actual_hashes, 'review_sha256': sha(review),
            'review_context_sha256': sha(context), 'video_probes': media,
            'frames': expected_frames, 'source_integrity_verified': True,
            'diagnostic_only': diagnostic,
            'physical_visibility_verified': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    require(not output.exists(), 'Choose a new receipt path')
    result = bind(args.source_dir)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'frames': result['frames'], 'receipt_sha256': sha(output)}))


if __name__ == '__main__':
    main()
