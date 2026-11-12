"""Independent saved-source audit for the six exact backing cases.

The returned diagnostic only proves software joins and decoding. A local
reviewer must inspect actual Native capture and pixels before acceptance.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from backing_safety_measurement import measure

PREFIX = 'heldout__C110779__NRS-484B-113-1__motor_vehicle_driver__'
CASES = {'backing_clear_vehicle', 'backing_near_vehicle', 'backing_vehicle_brakes',
         'backing_vehicle_contact', 'no_reverse_control', 'backing_pedestrian'}
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def audit(case, attempt):
    if not case.startswith(PREFIX) or case[len(PREFIX):] not in CASES:
        raise ValueError('Wrong exact delivery case')
    root = Path(attempt)

    def source(name):
        path = root / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing required source: ' + name)
        return path

    def rows(name):
        return [json.loads(line) for line in source(name).read_text().splitlines() if line]

    config = json.loads(source('config.json').read_text())
    result = json.loads(source('result.json').read_text())
    if (config.get('selected_case_id') != case or result.get('case_id') != case or
            config.get('law_id') != 'NRS-484B-113-1' or config.get('cell_id') != 'C110779' or
            config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('Exact backing identity differs')
    if result.get('physical_acceptance_claimed') or result.get('legal_acceptance_claimed'):
        raise ValueError('Unsupported fixture acceptance claim')
    corridor = source('backing_corridor_original.json')
    context = json.loads(source('backing_context.json').read_text())
    if context.get('corridor_source_sha256') != sha256(corridor.read_bytes()).hexdigest():
        raise ValueError('Original corridor/context hash differs')
    observed = measure(source('backing_motion.jsonl'), source('backing_contacts.jsonl'),
                       source('backing_context.json'))
    motion = rows('backing_motion.jsonl')
    contacts = rows('backing_contacts.jsonl')
    frames = rows('video_frames.jsonl')
    trace = rows('trace.jsonl')
    if not motion or len(motion) != len(contacts) or len(motion) != len(frames) or len(frames) != len(trace):
        raise ValueError('Original participant/time join incomplete')
    for index, (body, contact, frame, state) in enumerate(zip(motion, contacts, frames, trace)):
        identity = (body.get('frame'), body.get('time_s'))
        if (identity != (contact.get('frame'), contact.get('time_s')) or
                identity != (frame.get('carla_frame'), frame.get('time_s')) or
                identity != (state.get('frame'), state.get('time_s')) or
                frame.get('video_frame') != index):
            raise ValueError('Original participant/time join incomplete')
    if result.get('trace_reference') != 'trace.jsonl' or result.get('video_frame_map_reference') != 'video_frames.jsonl':
        raise ValueError('Original source references changed')
    if result.get('video_references') != [name + '.mkv' for name in CAMERAS]:
        raise ValueError('Four original camera references changed')
    if case.endswith('__no_reverse_control'):
        if observed['backing_onset_frame'] is not None:
            raise ValueError('Forward-only control contains reverse movement')
    elif observed['backing_onset_frame'] is None:
        raise ValueError('Backing movement absent from original source')
    decoded = {}
    for name in CAMERAS:
        media = source(name + '.mkv')
        full = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(media), '-f', 'null', '-'],
                              capture_output=True, text=True)
        if full.returncode:
            raise ValueError('Full video decode failed: ' + name)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-count_frames', '-show_entries', 'stream=nb_read_frames',
                                '-of', 'default=noprint_wrappers=1:nokey=1', str(media)],
                               capture_output=True, text=True)
        try:
            count = int(probe.stdout.strip())
        except ValueError as error:
            raise ValueError('Full video frame count unavailable: ' + name) from error
        if probe.returncode or count != len(frames):
            raise ValueError('Full video frame count changed: ' + name)
        decoded[name] = count
    sources = ('config.json', 'backing_corridor_original.json', 'backing_context.json',
               'backing_motion.jsonl', 'backing_contacts.jsonl', 'trace.jsonl',
               'video_frames.jsonl', 'result.json')
    return {'format': 'worker-delivery-audit', 'case_id': case, 'passed': True,
            'source_frames': len(frames), 'video_frames': decoded,
            'source_sha256': {name: sha256(source(name).read_bytes()).hexdigest() for name in sources},
            'physical_completion_check': result.get('physical_checks', {}).get('maneuver', {}).get('status'),
            'actual_pixels_check': 'Full decode and frame count only; actor visibility requires physical review',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt), indent=2))
