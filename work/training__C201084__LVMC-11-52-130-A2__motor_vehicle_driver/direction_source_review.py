"""Bind direction-branch raw traces to selected motion and saved originals.

This checks source identity and temporal completeness only. An actor pose or
traffic-light state is not a police instruction or applicable legal direction.
"""
import argparse
import json
from pathlib import Path

from fire_lane_survey import require
from source_measurement import read_lines, sha

HERE = Path(__file__).resolve().parent
SOURCES = {
    'officer_direction': ('police-officer-actor.jsonl', 'officer_actor_id',
                          'police_authority_verified'),
    'device_direction': ('traffic-control-device.jsonl', 'device_actor_id',
                         'direction_applicability_verified'),
}


def build(case, attempt, event_path, saved_path):
    require(case in SOURCES, 'Unknown direction branch')
    attempt, event_path, saved_path = map(Path, (attempt, event_path, saved_path))
    event = json.loads(event_path.read_text())
    saved = json.loads(saved_path.read_text())
    source_name, actor_key, authority_key = SOURCES[case]
    require(event.get('case') == case and
            event.get('format') == 'c201084-source-bound-motion-event-v1' and
            event.get('frames') == 600 and event.get('capture_hz') == 20 and
            event.get('diagnostic_fixture') is True and
            event.get('physical_or_legal_completion_claimed') is False,
            'Selected motion event identity differs')
    require(saved.get('passed') is True and
            saved.get('recorded_only') is True and
            saved.get('case_id') == HERE.name + '__' + case and
            saved.get('candidate_id') == 'primary' and
            saved.get('physical_acceptance_claimed') is False and
            saved.get('legal_acceptance_claimed') is False,
            'Selected saved processing identity differs')
    for name, digest in event['source_sha256'].items():
        require(sha(attempt / name) == digest and
                saved['original_source_hashes'].get(name) == digest,
                'Motion source or saved original differs: ' + name)
    source_path = attempt / source_name
    source_sha = sha(source_path)
    require(saved['original_source_hashes'].get(source_name) == source_sha,
            'Direction trace differs from saved original')
    frames = read_lines(attempt / 'video_frames.jsonl')
    actors = read_lines(attempt / 'native-actors.jsonl')
    directions = read_lines(source_path)
    require(len(frames) == len(actors) == len(directions) == 600,
            'Direction source is not 600-frame complete')
    actor_id = directions[0].get(actor_key)
    require(type(actor_id) is int and actor_id != actors[0].get('ego_actor_id'),
            'Direction source actor identity invalid')
    for index, (frame, actor, direction) in enumerate(zip(frames, actors, directions)):
        require(frame.get('video_frame') == index and
                direction.get('video_frame') == index and
                frame.get('carla_frame') == actor.get('frame') == direction.get('frame') and
                direction.get(actor_key) == actor_id and
                direction.get('source_kind') == 'synthetic_native_sample' and
                direction.get('statutory_necessity_verified') is False and
                direction.get('direction_applicability_verified') is False and
                direction.get(authority_key) is False,
                'Direction frame, actor or provenance differs')
    return {
        'format': 'c201084-selected-direction-source-binding-v1',
        'case_id': HERE.name + '__' + case,
        'motion_event_sha256': sha(event_path),
        'saved_processing_sha256': sha(saved_path),
        'direction_source': source_name,
        'direction_source_sha256': source_sha,
        'direction_actor_id': actor_id,
        'frames_joined': len(frames),
        'capture_hz': 20,
        'diagnostic_only': True,
        'original_native_observed': False,
        'authority_verified': False,
        'direction_applicability_verified': False,
        'statutory_necessity_verified': False,
        'physical_or_legal_completion_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=tuple(SOURCES), required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--event', type=Path, required=True)
    parser.add_argument('--saved', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Preserve existing direction binding')
    args.output.write_text(json.dumps(build(args.case, args.attempt, args.event,
                                            args.saved), indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
