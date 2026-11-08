"""Validate source-bound 480-frame sidewalk-camera visibility annotations."""
import hashlib
import json
import math
from pathlib import Path

from measure_saved import measure


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def camera_packet(saved_folder, review_file, video_source, expected_hashes=None):
    saved_folder, review_file, video_source = map(Path,(saved_folder,review_file,video_source))
    saved = measure(saved_folder)
    if not review_file.is_file() or not video_source.is_file():
        raise ValueError('Camera review or video source absent')
    kind = saved['source_kind']
    if kind == 'original_native':
        with video_source.open('rb') as source:
            magic = source.read(4)
        if video_source.suffix != '.mkv' or magic != bytes.fromhex('1a45dfa3'):
            raise ValueError('Original lossless Matroska video source absent')
    elif video_source.suffix != '.txt':
        raise ValueError('Synthetic video stub must be labelled text')
    hashes = {'review_sha256':sha(review_file), 'video_sha256':sha(video_source),
              'actor_sha256':sha(saved_folder/'native-observed.jsonl'),
              'video_mapping_sha256':sha(saved_folder/'video_frames.jsonl')}
    if expected_hashes is not None and hashes != expected_hashes:
        raise ValueError('Camera review source hash differs')
    annotations = lines(review_file)
    actors = lines(saved_folder/'native-observed.jsonl')
    mapping = lines(saved_folder/'video_frames.jsonl')
    if len(annotations) != 480:
        raise ValueError('Camera review frame count differs')
    visible = 0
    for index,(annotation,actor,frame) in enumerate(zip(annotations,actors,mapping)):
        if (annotation.get('frame') != index or annotation.get('video_frame') != index or
                annotation.get('native_frame') != actor['native_frame'] or
                annotation.get('time_s') != frame['time_s'] or
                annotation.get('source_kind') != kind or
                annotation.get('camera') != 'sidewalk' or
                annotation.get('review_method') not in ('manual_box_review','synthetic_cpu_box')):
            raise ValueError('Camera review Native/video frame join differs')
        if kind == 'original_native' and annotation['review_method'] != 'manual_box_review':
            raise ValueError('Original video requires manual box review provenance')
        if kind == 'synthetic_cpu' and annotation['review_method'] != 'synthetic_cpu_box':
            raise ValueError('Synthetic video review provenance differs')
        flag, box = annotation.get('subject_visible'),annotation.get('subject_box_xywh')
        if type(flag) is not bool:
            raise ValueError('Camera visibility flag invalid')
        if flag:
            if (not isinstance(box,list) or len(box)!=4 or
                    any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in box) or
                    box[0]<0 or box[1]<0 or box[2]<=0 or box[3]<=0 or
                    box[0]+box[2]>1 or box[1]+box[3]>1 or box[2]*box[3]<.001):
                raise ValueError('Visible subject box invalid')
            visible += 1
        elif box is not None:
            raise ValueError('Invisible subject has a box')
    return {'format':'c422978-heavy-camera-visibility-v1',
            'source':str(review_file.resolve()), 'sha256':hashes['review_sha256'],
            'source_kind':kind,'frames':480,'visible_frames':visible,
            'visible_fraction':visible/480,'source_hashes':hashes,
            'pixel_annotation_truth_verified':False,
            'physical_or_legal_acceptance':False}


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('saved_folder',type=Path)
    parser.add_argument('review_file',type=Path)
    parser.add_argument('video_source',type=Path)
    args=parser.parse_args()
    print(json.dumps(camera_packet(args.saved_folder,args.review_file,args.video_source),indent=2))
